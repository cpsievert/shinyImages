from shiny import App, reactive, render, ui
from chatlas import ChatOpenAI, content_image_url

from card import parse_to_card
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
            value="",
        ),
        ui.input_numeric(
            "n_words",
            "description word limit",
            value=100,
        ),
        ui.input_action_button("go", "Start"),
        ui.tags.script("""
        $(document).ready(function() {
            $(document).on('keypress', function(e) {
                if (e.which == 13) {  // 13 is the Enter key
                    $('#go').click();
                }
            });
        });
        """)
    ),
    ui.layout_columns(
        ui.div(
            ui.div(
                ui.output_ui(
                    "display_image",
                    style="padding-bottom: 10px; display: flex; justify-content: center; align-items: flex-start; overflow: hidden;"
                ),
                style="flex-shrink: 1;"
            ),
            ui.div(
                ui.output_ui("chat_container"),
                style="flex-grow: 1; overflow-y: auto; display: flex; flex-direction: column-reverse;"
            ),
            style="display: flex; flex-direction: column; height: calc(100vh - 40px - 40px); justify-content: space-between;"
        ),
        ui.div(id="card_container", style="display: grid; grid-template-columns: 1fr;"),
        col_widths={"sm": (12), "lg": (6)},
    ),
    title="Image Describer",
)


def server(input, output, session):
    chat = ui.Chat("chat")
    chat_client = ChatOpenAI(model="gpt-4o")

    @reactive.effect
    def _():
        chat_client.system_prompt = llm_prompt(input.style(), input.n_words())

    @render.ui
    def display_image():
        return ui.img(src=input.url(), style="max-height: 50vh; display: flex; justify-content: center; align-items: center; overflow: hidden;")

    def update_card(chunk, output):
        output.append(chunk)
        # try to update the card, but don't update if there's a parsing error
        try:
            card_update = parse_to_card("".join(output))
            ui.insert_ui(card_update, "#card_container", immediate=True)
            ui.remove_ui(selector="#card_container > div:not(:last-child)", immediate=True)
        except ValueError:
            pass
        return chunk

    @reactive.effect
    @reactive.event(input.go)
    async def start_chat():
        card_output = []
        stream = await chat_client.stream_async(
            "Describe this image",
            content_image_url(input.url())
        )
        stream2 = (update_card(chunk, card_output) async for chunk in stream)
        await chat.append_message_stream(stream2)

    # Allow the user to ask follow up questions
    @chat.on_user_submit
    async def _(user_input: str):
        card_output = []
        stream = await chat_client.stream_async(user_input)
        stream2 = (update_card(chunk, card_output) async for chunk in stream)
        await chat.append_message_stream(stream2)

    @render.ui
    @reactive.event(input.go)
    def chat_container():
        return [
            ui.chat_ui("chat")
        ]


app = App(app_ui, server)