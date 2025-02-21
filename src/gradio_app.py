import io
import gradio as gr
from PIL import Image
from datetime import datetime
from dateutil.relativedelta import relativedelta
from src.main import run_hedge_fund
from src.utils.analysts import ANALYST_ORDER
from src.utils.visualize import get_graph
from src.main import create_workflow
from src.utils.display import html_trading_output
from src.llm.models import AVAILABLE_MODELS, LLM_ORDER

def gradio_action(
        tickers: str,
        start_date: str,
        end_date: str,
        initial_cash: float,
        show_reasoning: bool,
        show_agent_graph: bool,
        selected_analysts: list,
        model_choice: str
    ):
    #Ticker
    ticker_list = [ticker.strip() for ticker in tickers.split(",") if ticker.strip()]

    if not ticker_list:
        raise gr.Error("Stock ticker symbols can't be empty")
    
    #Cash Position
    try:
        float(initial_cash)
    except (ValueError, TypeError):
        raise gr.Error("Invalid Initial Cash position")
    
    portfolio = {
        "cash": initial_cash,
        "positions": {ticker: 0 for ticker in tickers}
    }

    #Start/End Date
    if start_date:
        try:
            datetime.strptime(start_date, "%Y-%m-%d")
        except ValueError:
            raise gr.Error("Start date must be in YYYY-MM-DD format")

    if end_date:
        try:
            datetime.strptime(end_date, "%Y-%m-%d")
        except ValueError:
            raise gr.Error("End date must be in YYYY-MM-DD format")

    end_date = end_date or datetime.now().strftime("%Y-%m-%d")
    if not start_date:
        end_date_obj = datetime.strptime(end_date, "%Y-%m-%d")
        start_date = (end_date_obj - relativedelta(months=3)).strftime("%Y-%m-%d")

    #Analysts
    if not selected_analysts:
        raise gr.Error("You must select at least one analyst.")
    analyst_dict = dict(ANALYST_ORDER)
    selected_analysts = [analyst_dict[analyst] for analyst in selected_analysts]
    
    #Workflow Graph
    graph_image = gr.update(visible=False) 
    if show_agent_graph:
        workflow = create_workflow(selected_analysts)
        app = workflow.compile()
        graph_bytes = get_graph(app)
        pil_image = Image.open(io.BytesIO(graph_bytes))
        graph_image = gr.update(value=pil_image, visible=True) 

    #Model
    model_info = next(model for model in AVAILABLE_MODELS if model.display_name == model_choice)
    model_provider = model_info.provider.value
    model_name = model_info.model_name

    try:
        result = run_hedge_fund(
            tickers=ticker_list,
            start_date=start_date,
            end_date=end_date,
            portfolio=portfolio,
            show_reasoning=show_reasoning,
            selected_analysts=selected_analysts,
            model_name=model_name,
            model_provider=model_provider,
        )

        trading_output = html_trading_output(result)
        return trading_output, graph_image
    except Exception as ex:
        return f"<p>Something went wrong, {ex}<p>", graph_image


# Create the Gradio interface
def create_gradio_interface():
    
    analyst_choices = [choice[0] for choice in ANALYST_ORDER]
    model_choices = [choice[0] for choice in LLM_ORDER]
    end_date_placeholder = datetime.now().strftime("%Y-%m-%d")
    start_date_placeholder = (datetime.now() - relativedelta(months=3)).strftime("%Y-%m-%d")
    
    with gr.Blocks() as interface:
        gr.Markdown("# Hedge Fund Trading System")
        
        with gr.Row():
            with gr.Column():
                with gr.Row():
                    tickers_input = gr.Textbox(label="Enter Ticker Symbols (comma separated)", placeholder="AAPL, TSLA, MSFT")
                    initial_cash_input = gr.Number(value=100000.0, label="Initial Cash Position")
                    
                with gr.Row():
                    start_date_input = gr.Textbox(label="Start Date (YYYY-MM-DD)", placeholder=start_date_placeholder)
                    end_date_input = gr.Textbox(label="End Date (YYYY-MM-DD)", placeholder=end_date_placeholder)
                    with gr.Column():
                        show_reasoning_checkbox = gr.Checkbox(label="Show Reasoning from Each Agent")
                        show_agent_graph_checkbox = gr.Checkbox(label="Show Agent Graph")
                
                with gr.Row():
                    analyst_select = gr.CheckboxGroup(choices=analyst_choices, label="Select Analysts", value=analyst_choices)
                    model_select = gr.Dropdown(choices=model_choices, label="Select LLM Model", value=model_choices[0])
                
                run_button = gr.Button("Run", variant="primary")
                graph_image = gr.Image(label="Agent Graph", interactive=False, visible=False, type="pil")

            
            output = gr.HTML(label="Trading Output", container=True, show_label=True, min_height=300, max_height=600)

        run_button.click(
            gradio_action, 
            inputs=[tickers_input, start_date_input, end_date_input, initial_cash_input, show_reasoning_checkbox, show_agent_graph_checkbox, analyst_select, model_select],
            outputs=[output, graph_image]
        )

    return interface

if __name__ == "__main__":
    gradio_app = create_gradio_interface()
    gradio_app.launch(share=False)
