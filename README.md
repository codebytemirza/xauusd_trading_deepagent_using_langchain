# 7MS Trading Strategy Deep Agent with MT5 Integration

A powerful AI-driven trading agent that automates the **7 Market Structure (7MS)** strategy using [MetaTrader 5](https://www.metatrader5.com/). This system combines advanced market analysis, liquidity sweep detection, and human-in-the-loop (HITL) execution to provide a professional automated trading solution.

## 🚀 Key Features

- **Logic-Based Strategy**: Implements the strict 7MS strategy rules (Order Blocks, Liquidity Sweeps, MSS/POI).
- **Deep Reasoning**: Uses an Agentic workflow to analyze trend, validate setups, and calculate risk.
- **MetaTrader 5 Integration**: Direct connection for real-time data fetching and order execution.
- **Human-in-the-Loop**: The agent proposes trades, but **YOU** have the final say (Approve/Reject/Edit) via the UI.
- **Beautiful GUI**: Built with Gradio for a stunning, interactive dashboard.
- **Visual Feedback**: Real-time phase indicators, beautifully formatted trade plans, and position monitoring.

## 📊 Strategy Workflow

The agent follows a strict decision tree to identify high-probability setups.

![Trading Agent Flow](flow.svg)

## 🛠️ Setup Guide

### Prerequisites

1.  **MetaTrader 5 (MT5)**: Installed and logged into your broker account.
    - _Note: "Auto Trading" must be enabled in MT5 toolbar._
2.  **Python 3.10+**: Installed on your system.
3.  **OpenAI API Key**: required for the deep reasoning agent.

### Installation

1.  **Clone the Repository**

    ```bash
    git clone <your-repo-url>
    cd trading_agent
    ```

2.  **Create a Virtual Environment**

    ```bash
    python -m venv .venv
    # Windows
    .venv\Scripts\activate
    # Mac/Linux
    source .venv/bin/activate
    ```

3.  **Install Dependencies**

    ```bash
    pip install -r requirements.txt
    ```

    _(If `requirements.txt` is missing, install manually)_:

    ```bash
    pip install metatrader5 langchain-openai langchain-core deepagents langgraph pandas numpy python-dotenv gradio
    ```

4.  **Configure Environment**
    - Rename `.env.example` to `.env`:
      ```bash
      # Windows
      copy .env.example .env
      # Mac/Linux
      cp .env.example .env
      ```
    - Open `.env` and add your API key:
      ```env
      OPENAI_API_KEY=sk-your-openai-api-key-here
      ```

### Usage

1.  **Open MetaTrader 5** and ensure your account is connected.
2.  **Run the Agent GUI**:
    ```bash
    python agent_app.py
    ```
3.  **Access the Dashboard**:
    - Open your browser and navigate to the local URL shown in the terminal (usually `http://127.0.0.1:7860`).
4.  **Start Trading**:
    - Enter the symbol (e.g., `XAUUSD`) in the dashboard.
    - Click **Start Analysis**.
    - Watch the agent analyze the market step-by-step.
    - **Approve** valid trade setups when prompted!

## ⚠️ Risk Warning

Trading Forex and CFD involves significant risk. This software is an educational tool and an automation assistant. The 7MS strategy does not guarantee profits. Use at your own risk. **Always test on a DEMO account first.**

---

_Built with ❤️ for 7MS Traders_
