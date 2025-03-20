from pathlib import Path

from shiny import App, reactive, render, ui
from chatlas import ChatOpenAI, content_image_url

from card import extract_image_details, image_details_ui
from prompt import llm_prompt

app_ui = ui.page_sidebar(
    ui.sidebar(
        ui.input_text(
            "url",
            "Image URL",
            value="https://live.staticflickr.com/65535/52378413572_14860a5ba1_b.jpg",
        ),
        ui.input_text(
            "style",
            "In the style of",
            value="Shakespeare",
        ),
        ui.input_numeric(
            "n_words",
            "Description word limit",
            value=100,
        ),
        ui.input_task_button("go", "Describe Image"),
    ),
    ui.layout_sidebar(
        ui.sidebar(
            ui.output_ui("chat_container"),
            open="closed",
            position="right",
        ),
        ui.layout_columns(
            ui.output_ui("image_container", fill=True, fillable=True),
            ui.output_ui("card_container", fill=True, fillable=True),
            col_widths={"sm": (12), "lg": (6)},
        ),
        id="chat_sidebar",
        fill=True,
        padding="3rem",
        border=False
    ),
    ui.tags.style(".card-header p { margin-bottom: 0; }"),
    ui.tags.script(src="keypress.js"),
    fillable=True,
    # TODO: padding doesn't work here?!
    padding=0,
    title="Image Describer",
)


def server(input, output, session):
    chat = ui.Chat("chat")
    chat_client = ChatOpenAI(model="gpt-4o")

    card_title = ui.MarkdownStream("card_title")
    card_body = ui.MarkdownStream("card_body")

    @reactive.effect
    def _():
        chat_client.system_prompt = llm_prompt(input.style(), input.n_words())

    @render.ui
    def image_container():
        return ui.img(src=input.url(), class_="html-fill-item rounded")
    
    @render.ui
    def card_container():
        if input.go() == 0:
            return ui.card(
                {"class": "text-muted"},
                "No description yet (press 'Enter')"
            )
        else:
            return ui.card(
                ui.card_header(
                    {"class": "bg-dark fw-bold fs-3"},
                    ui.output_markdown_stream("card_title")
                ),
                ui.output_markdown_stream("card_body", auto_scroll=False),
            )

    # As .append_message_stream() is iterating through the generator, accumulate contents
    # so we can parse it, extract the image details, and update the card title and body.
    async def stream_wrapper(stream):
        all_content: str = ""
        async with card_body.stream_context() as body:
            async with card_title.stream_context() as title:
                async for chunk in stream:
                    all_content += chunk
                    deats = extract_image_details(all_content)
                    await title.replace(deats.get("title"))
                    await body.replace(image_details_ui(deats))
                    yield chunk

    @reactive.effect
    @reactive.event(input.go)
    async def start_chat():
        stream = await chat_client.stream_async(
            "Describe this image",
            content_image_url(input.url())
        )
        await chat.append_message_stream(stream_wrapper(stream))

    # Allow the user to ask follow up questions
    @chat.on_user_submit
    async def _(user_input: str):
        stream = await chat_client.stream_async(user_input)
        await chat.append_message_stream(stream_wrapper(stream))

    @render.ui
    def chat_container():
        if input.go() == 0:
            return "A chat will appear here once there is a description"
        else:
            return ui.chat_ui("chat")
        
    @reactive.effect
    def _():
        ui.update_sidebar(id="chat_sidebar", show=input.go() % 2 == 1)

 
app = App(app_ui, server, static_assets=Path(__file__).parent / "www")
