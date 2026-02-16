# LangSmith Integration Guide

## Overview

LangSmith provides comprehensive observability for your MCP server, tracking:
- 📊 **Tool Usage**: Every MCP tool invocation with arguments
- ⏱️ **Performance**: Execution time for each operation
- 💰 **Token Costs**: Track API usage and costs
- 🐛 **Errors**: Detailed error traces with context
- 📈 **Analytics**: Usage patterns and trends over time

## Quick Start

### 1. Get Your API Key

1. Visit [LangSmith](https://smith.langchain.com/)
2. Sign up or log in
3. Navigate to **Settings** → **API Keys**
4. Create a new API key

### 2. Configure Environment Variables

Add to your `.env` file:

```bash
# LangSmith Configuration
LANGSMITH_API_KEY=lsv2_pt_xxxxxxxxxxxxxxxxxxxxx
LANGSMITH_PROJECT=code-analysis-mcp
LANGCHAIN_TRACING_V2=true
LANGCHAIN_ENDPOINT=https://api.smith.langchain.com
```

**Project naming tips:**
- Use descriptive names: `prod-code-analysis`, `dev-mcp-server`
- Separate environments: `code-analysis-dev`, `code-analysis-prod`
- Include dates for temporary projects: `code-analysis-2026-02`

### 3. Install LangSmith Package

The package is already included in `requirements.txt`. If installing manually:

```bash
pip install langsmith>=0.1.0
```

### 4. Restart Services

```bash
docker-compose restart mcp
```

Or rebuild if needed:

```bash
docker-compose build mcp
docker-compose up -d mcp
```

## Viewing Your Data

### Dashboard Access

1. Go to [LangSmith Dashboard](https://smith.langchain.com/)
2. Select your project from the dropdown
3. View traces, analytics, and metrics

### What You'll See

#### Traces Page
- **List of all tool calls** with timestamps
- **Execution time** for each operation
- **Success/error status**
- **Input/output data** (click to expand)

#### Analytics Page
- **Usage trends** over time
- **Most used tools**
- **Average execution times**
- **Error rates**

#### Costs Page
- **API call counts**
- **Token usage** (if LLM calls are made)
- **Estimated costs**

## Understanding Tool Traces

Each MCP tool call creates a trace with:

```json
{
  "name": "mcp_tool_analyze_project",
  "type": "tool",
  "inputs": {
    "arguments": {
      "path": "/app/src/core",
      "max_depth": 10
    }
  },
  "outputs": {
    "result": "{ ... analysis results ... }"
  },
  "metadata": {
    "tool_name": "analyze_project",
    "execution_time_seconds": 2.34,
    "status": "success"
  }
}
```

## Best Practices

### 1. Use Separate Projects for Environments

```bash
# Development
LANGSMITH_PROJECT=code-analysis-dev

# Production
LANGSMITH_PROJECT=code-analysis-prod

# Testing
LANGSMITH_PROJECT=code-analysis-test
```

### 2. Add Custom Tags

You can extend tracking by adding tags in your code:

```python
# In tool handlers, add custom metadata
metadata = {
    "user_id": "user123",
    "environment": "production",
    "version": "1.0.0"
}
```

### 3. Monitor Performance

Set up alerts for:
- **Slow operations** (execution time > 10s)
- **High error rates** (> 5%)
- **Unusual usage patterns**

### 4. Review Regularly

- Check dashboard weekly
- Identify bottlenecks
- Optimize slow tools
- Fix recurring errors

## Troubleshooting

### Traces Not Appearing

**Issue**: No traces showing in LangSmith dashboard

**Solutions**:
1. Verify API key is correct
   ```bash
   echo $LANGSMITH_API_KEY
   ```

2. Check environment variables in container
   ```bash
   docker exec ai_analyst_mcp env | grep LANGSMITH
   ```

3. Check logs for errors
   ```bash
   docker logs ai_analyst_mcp | grep -i langsmith
   ```

4. Verify network connectivity
   ```bash
   docker exec ai_analyst_mcp curl -I https://api.smith.langchain.com
   ```

### API Key Errors

**Issue**: "Invalid API key" errors

**Solutions**:
- Ensure API key starts with `lsv2_pt_`
- Check for extra spaces in `.env` file
- Regenerate key in LangSmith dashboard
- Restart Docker container after updating `.env`

### High Costs

**Issue**: Unexpected LangSmith costs

**Notes**:
- LangSmith free tier: **5,000 traces/month**
- Paid plans start at **$39/month** for 100K traces
- MCP tool calls are lightweight (minimal data)
- Most costs come from LLM token usage, not tracing

**Solutions**:
- Monitor trace count in dashboard
- Disable tracing in non-essential environments
- Use sampling for high-volume tools

### Performance Impact

**Issue**: Concerned about overhead

**Reality**:
- Tracing adds **< 50ms** per tool call
- Async logging doesn't block execution
- Network calls are non-blocking
- Minimal CPU/memory overhead

**To disable**:
```bash
# Remove or comment out in .env
# LANGSMITH_API_KEY=...
```

## Advanced Configuration

### Sampling

To trace only a percentage of calls:

```python
# In small_mcp.py, add sampling logic
import random

if random.random() < 0.1:  # 10% sampling
    # Log to LangSmith
    pass
```

### Custom Metadata

Add business-specific metadata:

```python
metadata = {
    "org_id": os.getenv("ORG_ID"),
    "deployment": os.getenv("DEPLOYMENT_ENV"),
    "region": "us-west-2",
    "custom_field": "value"
}
```

### Filtering Sensitive Data

To exclude sensitive information:

```python
# Truncate or mask sensitive fields
safe_args = {
    k: "***" if k in ["api_key", "password"] else v
    for k, v in arguments.items()
}
```

## Cost Breakdown

### Free Tier (Most users)
- ✅ 5,000 traces/month
- ✅ 30 days retention
- ✅ Basic analytics
- ✅ Community support

### Developer Plan ($39/mo)
- ✅ 100,000 traces/month
- ✅ 90 days retention
- ✅ Advanced analytics
- ✅ Email support

### Team Plan ($99/mo)
- ✅ 500,000 traces/month
- ✅ 1 year retention
- ✅ Team collaboration
- ✅ Priority support

## Integration Examples

### Example: Tracking Code Analysis

When you run:
```python
result = await call_tool("analyze_project", {"path": "/app/src"})
```

LangSmith records:
- Tool: `mcp_tool_analyze_project`
- Input: `{"path": "/app/src"}`
- Duration: `3.2 seconds`
- Output: Analysis results (truncated)
- Status: `success` or `error`

### Example: Error Tracking

If a tool fails:
```python
try:
    result = await call_tool("invalid_tool", {})
except Exception as e:
    # LangSmith automatically logs:
    # - Error message
    # - Stack trace
    # - Failed inputs
    # - Execution time before failure
    pass
```

## Support

- 📚 [LangSmith Docs](https://docs.smith.langchain.com/)
- 💬 [LangChain Discord](https://discord.gg/langchain)
- 🐛 [GitHub Issues](https://github.com/langchain-ai/langsmith-sdk)
- 📧 Email: support@langchain.com

## FAQ

### Q: Is LangSmith required?
**A:** No, it's completely optional. The MCP server works without it.

### Q: What data is sent to LangSmith?
**A:** Tool names, arguments, execution times, and results (truncated to 500 chars).

### Q: Can I self-host LangSmith?
**A:** No, it's a hosted service only. For self-hosted alternatives, consider Langfuse or Phoenix.

### Q: Does it track actual token usage?
**A:** Yes, when LLM calls are made (e.g., in chat service), LangSmith automatically tracks tokens.

### Q: How do I export data?
**A:** Use the LangSmith API or export from the dashboard (CSV/JSON).

### Q: Can I delete traces?
**A:** Yes, from the dashboard or via API. Deleted traces don't count toward your quota.

---

**Next Steps:**
1. ✅ Set up your API key
2. ✅ Configure environment variables
3. ✅ Restart MCP server
4. ✅ Make some tool calls
5. ✅ Check the dashboard
6. ✅ Set up monitoring/alerts

Happy tracking! 🚀
