# 📚 Airweave Examples

Welcome to the Airweave examples! These Jupyter notebooks demonstrate real-world use cases and best practices for using Airweave to connect your data sources and build AI-powered applications.

## 🚀 Getting Started

### Prerequisites

Before running the examples, make sure you have:

1. **Python 3.8+** installed
2. **Jupyter Notebook** or **JupyterLab** installed
3. **API Keys** for the services you want to connect:
   - Airweave API Key (get one at [app.airweave.ai](https://app.airweave.ai))
   - GitHub Personal Access Token (optional)
   - Stripe API Key (optional)
   - OpenAI API Key (for notebooks 2 & 3)

### Installation

Install the required packages:

```bash
pip install airweave-sdk jupyter openai python-dotenv
```

## 📓 Available Examples

### 1. Getting Started with Airweave (`01_getting_started_with_airweave.ipynb`)

**What you'll learn:**
- ✅ How to create and manage collections
- ✅ Connecting multiple data sources (GitHub & Stripe)
- ✅ Monitoring sync progress in real-time
- ✅ Searching across connected data sources

**Time to complete:** ~15 minutes

**Perfect for:** First-time users who want to understand Airweave's core functionality

### 2. Building AI Agents with Function Calling (`02_ai_agent_with_function_calling.ipynb`)

**What you'll learn:**
- ✅ Define Airweave search as a function for OpenAI
- ✅ Create an agent that intelligently searches your data
- ✅ Build a conversational interface with memory
- ✅ Handle complex queries requiring multiple searches

**Time to complete:** ~20 minutes

**Perfect for:** Developers wanting to integrate Airweave with OpenAI's function calling feature

### 3. Using Airweave MCP Server (`03_mcp_server_integration.ipynb`)

**What you'll learn:**
- ✅ Connect to Airweave's MCP (Model Context Protocol) server
- ✅ Use OpenAI's remote MCP tool feature
- ✅ Build agents that can search via MCP
- ✅ Compare MCP vs function calling approaches

**Time to complete:** ~15 minutes

**Perfect for:** Advanced users exploring standardized tool protocols

## 🏃‍♂️ Running the Examples

1. **Start Jupyter Notebook:**
   ```bash
   jupyter notebook
   ```

2. **Navigate to the examples folder** and open the notebook you want to run

3. **Update the API keys** in the first few cells with your actual credentials

4. **Run the cells** in order (Shift + Enter)

## 📊 Example Progression

The notebooks are designed to be completed in order:

1. **Start with notebook 1** to set up your Airweave collection and data sources
2. **Move to notebook 2** to build an AI agent using function calling
3. **Explore notebook 3** to see how MCP integration provides a standardized approach

Each notebook builds on concepts from the previous ones, but they can also be run independently if you already have a collection set up.

## 💡 Tips

- **Use environment variables** for API keys instead of hardcoding them
- **Start with test/sandbox accounts** when connecting services like Stripe
- **Monitor the Airweave dashboard** at [app.airweave.ai](https://app.airweave.ai) to see your syncs in action
- **Save your collection ID** from notebook 1 - you'll need it for notebooks 2 and 3
- **Join our Discord** at [discord.gg/484HY9Ehxt](https://discord.gg/484HY9Ehxt) if you need help!

## 🤝 Contributing

Have an interesting use case or example? We'd love to see it! Please:

1. Fork the repository
2. Create your example notebook
3. Submit a pull request

Make sure your example:
- Has clear documentation and comments
- Uses realistic but safe sample data
- Follows the existing naming pattern (`XX_example_name.ipynb`)
- Includes proper error handling

## 📚 More Resources

- [Airweave Documentation](https://docs.airweave.ai)
- [API Reference](https://docs.airweave.ai/api-reference)
- [Source Connectors Guide](https://docs.airweave.ai/connectors)
- [MCP Server Guide](https://docs.airweave.ai/mcp-server)
- [GitHub Repository](https://github.com/airweave-ai/airweave)

---

Happy coding! 🎉 If you build something cool with Airweave, let us know on [Discord](https://discord.gg/484HY9Ehxt) or [Twitter](https://twitter.com/airweave_ai)!
