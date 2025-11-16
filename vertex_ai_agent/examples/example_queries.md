# Example Queries for PI System Assistant

This document provides example queries you can use with your Vertex AI PI System Assistant agent.

## 🔍 Semantic Search

### Finding Equipment by Type

```
"Find all temperature sensors in the plant"
```
Expected: List of AF elements with temperature-related names or templates

```
"Show me all pumps"
```
Expected: List of pump equipment from the AF hierarchy

```
"List all equipment in Unit 100"
```
Expected: All AF elements within Unit 100

### Template-Based Search

```
"Find all elements using the Tank template"
```
Expected: Elements based on specific AF template

```
"Show me all analog sensors"
```
Expected: Elements with analog sensor templates

### Location-Based Search

```
"What equipment is in the North Plant area?"
```
Expected: Elements in the North Plant hierarchy

```
"List all sensors in Building A, Floor 2"
```
Expected: Equipment in specific location hierarchy

## 📊 Data Retrieval

### Current Values

```
"Get current values for temperature sensor TS-101"
```
Expected: Latest reading with timestamp, value, and units

```
"Show me real-time data for all attributes of pump P-200"
```
Expected: StreamSet of current values for all pump attributes

### Historical Data

```
"Retrieve the last 24 hours of data for sensor TS-101"
```
Expected: Recorded values for past day

```
"Get hourly averages for the past week for flow meter FM-500"
```
Expected: Interpolated hourly data points

```
"Show me data from January 1, 2024 to January 7, 2024 for pressure sensor PS-300"
```
Expected: Historical data for specific date range

### Multi-Attribute Queries

```
"Get all process variables for reactor R-100 for the last 48 hours"
```
Expected: Multiple attributes (temp, pressure, level, etc.)

```
"Show me the operating parameters for compressor C-450 over the past month"
```
Expected: All relevant compressor metrics

## 📈 Advanced Analytics

### Trending and Patterns

```
"Analyze the temperature trend for sensor TS-101 over the past week"
```
Expected: Trend analysis with insights

```
"Compare flow rates between FM-100 and FM-200 for the last 30 days"
```
Expected: Comparative analysis

### Anomaly Detection

```
"Are there any unusual patterns in the pressure data for PS-300?"
```
Expected: Outliers and anomaly identification

```
"Identify any data quality issues in sensor readings for the past 24 hours"
```
Expected: Bad data, gaps, or questionable values flagged

### Performance Metrics

```
"Calculate the average runtime for pump P-150 over the past month"
```
Expected: Operational statistics

```
"What's the utilization rate of reactor R-100 in the last quarter?"
```
Expected: Performance KPIs

## 🔮 Forecasting

### Basic Forecasting

```
"Forecast the next 7 days for temperature sensor TS-101"
```
Expected: 7-day prediction with confidence intervals

```
"Predict power consumption for the next 30 days based on last 90 days"
```
Expected: Monthly forecast with trend analysis

### Detailed Forecasting

```
"Generate a forecast for flow meter FM-200 with 60 days of training data predicting 14 days ahead"
```
Expected: Detailed forecast with model metrics

```
"Create a production forecast including seasonality analysis"
```
Expected: Forecast considering seasonal patterns

### Forecast Analysis

```
"What's the expected trend for temperature over the next week?"
```
Expected: Trend direction and magnitude

```
"How confident is the forecast for sensor XYZ?"
```
Expected: Model performance metrics (RMSE, MAPE, R²)

## 🏥 System Health & Monitoring

### Health Checks

```
"Check PI System health status"
```
Expected: Overall system health report

```
"What's the status of the PI Data Archive?"
```
Expected: Data server status and metrics

```
"Show me AF Server status and database information"
```
Expected: Asset server details

### Performance Monitoring

```
"What's the API response time?"
```
Expected: Performance metrics

```
"How many elements are indexed in the vector database?"
```
Expected: Index statistics

### Diagnostics

```
"Are there any connection issues with PI System?"
```
Expected: Connectivity diagnostics

```
"Check the last indexing operation status"
```
Expected: Indexing health and timing

## 🔧 Batch Operations

### Multiple Elements

```
"Get attributes for elements E-100, E-101, and E-102"
```
Expected: Batch attribute retrieval

```
"Retrieve current values for all sensors in list: [TS-101, PS-200, FM-300]"
```
Expected: Batch current value retrieval

### Complex Workflows

```
"Find all pumps, get their power consumption attributes, and show last 24 hours of data"
```
Expected: Multi-step operation with search, attribute lookup, and data retrieval

```
"List all reactors, check their current temperatures, and flag any above 350°F"
```
Expected: Search, data retrieval, and conditional analysis

## 💡 Best Practice Queries

### Clear and Specific

✅ Good: "Get recorded values for temperature sensor TS-101 from January 1 to January 7, 2024"

❌ Avoid: "Get some data"

### Use Proper Names

✅ Good: "Show me data for pump P-150"

❌ Avoid: "Show data for the pump"

### Specify Time Ranges

✅ Good: "Last 24 hours of data for sensor TS-101"

❌ Avoid: "Recent data for TS-101" (ambiguous)

### Be Explicit About Requirements

✅ Good: "Find all temperature sensors with values above 200°F in the last hour"

❌ Avoid: "Find hot sensors" (subjective)

## 🎯 Domain-Specific Examples

### Oil & Gas

```
"Monitor wellhead pressure for Well-A-123 over the past week"
"Forecast production rates for the next month"
"Identify any flow anomalies in Pipeline-5"
```

### Manufacturing

```
"Track machine efficiency for Line-3 in the last shift"
"Compare quality metrics between Batch-A and Batch-B"
"Predict maintenance needs for conveyor belt CB-450"
```

### Utilities

```
"Monitor power grid frequency for the past 24 hours"
"Forecast energy demand for next week"
"Analyze transformer load patterns"
```

### Chemical Processing

```
"Monitor reactor temperature and pressure for R-300"
"Track batch cycle times for the past month"
"Predict catalyst life remaining"
```

## 🚀 Advanced Use Cases

### Root Cause Analysis

```
"When did pressure sensor PS-200 start showing abnormal values? What other sensors changed at the same time?"
```

### Predictive Maintenance

```
"Based on vibration data, predict when pump P-150 will need maintenance"
```

### Energy Optimization

```
"Identify periods of high energy consumption and suggest optimization opportunities"
```

### Quality Control

```
"Correlate temperature variations with product quality metrics for Batch-12345"
```

## 📝 Tips for Better Results

1. **Be specific about time ranges**: Use exact dates or relative times (last 24 hours, past week)

2. **Use equipment names or IDs**: Reference specific tags or element names

3. **Specify data granularity**: Mention if you want raw, interpolated, or aggregated data

4. **Ask follow-up questions**: The agent maintains context, so you can refine queries

5. **Request explanations**: Ask "why" or "explain" to get insights, not just data

6. **Combine operations**: Request multi-step workflows in a single query

## 🔄 Iterative Querying

Start broad, then narrow down:

```
1. "Find all temperature sensors"
2. "Show me sensors in Unit 100"
3. "Get data for TS-101 in Unit 100"
4. "What's the trend over the past week?"
5. "Forecast the next 7 days"
```

## ⚙️ Customization

You can customize these queries based on:
- Your specific AF database structure
- Your naming conventions
- Your operational needs
- Your industry requirements

Happy querying! 🎉
