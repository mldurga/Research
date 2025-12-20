# Example Email Format

This document shows example email formats that the system can process.

## Example 1: Simple Sensor Readings

### Email Details
- **Subject:** PI Data Update - Hourly Readings
- **Attachment:** sensor_data.pdf

### PDF Content Example
```
SENSOR READINGS REPORT
Date: 2025-12-20
Time: 14:00:00

Temperature Sensors:
- TIC-101: 75.2°C
- TIC-102: 68.5°C
- TIC-103: 82.1°C

Pressure Sensors:
- PIC-201: 150.3 PSI
- PIC-202: 145.8 PSI

Flow Meters:
- FIC-301: 320.5 GPM
- FIC-302: 285.3 GPM
```

### Expected Extraction Result
```json
[
  {
    "tag_name": "TIC-101",
    "value": 75.2,
    "unit": "°C",
    "timestamp": "2025-12-20T14:00:00"
  },
  {
    "tag_name": "TIC-102",
    "value": 68.5,
    "unit": "°C",
    "timestamp": "2025-12-20T14:00:00"
  },
  {
    "tag_name": "TIC-103",
    "value": 82.1,
    "unit": "°C",
    "timestamp": "2025-12-20T14:00:00"
  },
  {
    "tag_name": "PIC-201",
    "value": 150.3,
    "unit": "PSI",
    "timestamp": "2025-12-20T14:00:00"
  },
  {
    "tag_name": "PIC-202",
    "value": 145.8,
    "unit": "PSI",
    "timestamp": "2025-12-20T14:00:00"
  },
  {
    "tag_name": "FIC-301",
    "value": 320.5,
    "unit": "GPM",
    "timestamp": "2025-12-20T14:00:00"
  },
  {
    "tag_name": "FIC-302",
    "value": 285.3,
    "unit": "GPM",
    "timestamp": "2025-12-20T14:00:00"
  }
]
```

## Example 2: Production Summary

### Email Details
- **Subject:** PI Data Update - Daily Production
- **Attachment:** production_report.pdf

### PDF Content Example
```
DAILY PRODUCTION SUMMARY
Facility: ADNOC Plant A
Date: December 20, 2025

Production Metrics:
====================
Oil Production: 25,450 barrels
Gas Production: 12,350 MCF
Water Cut: 15.2%

Key Performance Indicators:
============================
Uptime: 98.5%
Efficiency: 92.3%
Energy Consumption: 1,250 MWh
```

### Expected Extraction Result
```json
[
  {
    "tag_name": "OIL_PRODUCTION",
    "value": 25450,
    "unit": "barrels",
    "timestamp": "2025-12-20T00:00:00"
  },
  {
    "tag_name": "GAS_PRODUCTION",
    "value": 12350,
    "unit": "MCF",
    "timestamp": "2025-12-20T00:00:00"
  },
  {
    "tag_name": "WATER_CUT",
    "value": 15.2,
    "unit": "%",
    "timestamp": "2025-12-20T00:00:00"
  },
  {
    "tag_name": "UPTIME",
    "value": 98.5,
    "unit": "%",
    "timestamp": "2025-12-20T00:00:00"
  },
  {
    "tag_name": "EFFICIENCY",
    "value": 92.3,
    "unit": "%",
    "timestamp": "2025-12-20T00:00:00"
  },
  {
    "tag_name": "ENERGY_CONSUMPTION",
    "value": 1250,
    "unit": "MWh",
    "timestamp": "2025-12-20T00:00:00"
  }
]
```

## Example 3: Lab Analysis Results

### Email Details
- **Subject:** PI Data Update - Lab Results
- **Attachment:** lab_analysis.pdf

### PDF Content Example
```
LABORATORY ANALYSIS REPORT
Sample ID: LAB-2025-001234
Analysis Date: 2025-12-20 10:30 AM

Crude Oil Properties:
---------------------
API Gravity: 34.5
Sulfur Content: 1.2% weight
Viscosity @ 40°C: 15.8 cSt
Pour Point: -12°C
Flash Point: 65°C

Water Content: 0.3% volume
Salt Content: 25 PTB
```

### Expected Extraction Result
```json
[
  {
    "tag_name": "API_GRAVITY",
    "value": 34.5,
    "timestamp": "2025-12-20T10:30:00"
  },
  {
    "tag_name": "SULFUR_CONTENT",
    "value": 1.2,
    "unit": "% weight",
    "timestamp": "2025-12-20T10:30:00"
  },
  {
    "tag_name": "VISCOSITY_40C",
    "value": 15.8,
    "unit": "cSt",
    "timestamp": "2025-12-20T10:30:00"
  },
  {
    "tag_name": "POUR_POINT",
    "value": -12,
    "unit": "°C",
    "timestamp": "2025-12-20T10:30:00"
  },
  {
    "tag_name": "FLASH_POINT",
    "value": 65,
    "unit": "°C",
    "timestamp": "2025-12-20T10:30:00"
  },
  {
    "tag_name": "WATER_CONTENT",
    "value": 0.3,
    "unit": "% volume",
    "timestamp": "2025-12-20T10:30:00"
  },
  {
    "tag_name": "SALT_CONTENT",
    "value": 25,
    "unit": "PTB",
    "timestamp": "2025-12-20T10:30:00"
  }
]
```

## Tips for Best Results

1. **Clear Tag Names**: Use consistent naming conventions (e.g., TIC-101, PIC-201)
2. **Explicit Values**: Write numbers clearly with units
3. **Timestamps**: Include date and time when available
4. **Structured Format**: Use clear sections and labels
5. **Avoid Ambiguity**: Be explicit about what each value represents

## Customizing Extraction

You can customize the extraction prompt in `config/config.yaml`:

```yaml
ollama:
  system_prompt: |
    Extract process data from the following industrial report.
    Focus on:
    - Sensor/tag names (e.g., TIC-101, PIC-201)
    - Numerical values
    - Units of measurement
    - Timestamps

    Return as JSON array with fields:
    - tag_name: The sensor/tag identifier
    - value: The numerical value
    - unit: Unit of measurement
    - timestamp: ISO format timestamp

    For ADNOC naming conventions:
    - TIC = Temperature Indicating Controller
    - PIC = Pressure Indicating Controller
    - FIC = Flow Indicating Controller
```

## Testing

To test the system:

1. Create a test PDF with sample data
2. Send an email with subject containing "PI Data Update"
3. Attach the PDF
4. Monitor logs: `logs/pi_notification.log`
5. Check PI System for written values

## Troubleshooting

### No Data Extracted

- **Check:** PDF has readable text (not scanned image)
- **Check:** Text is clearly formatted with tag names and values
- **Check:** Ollama is processing the correct model

### Wrong Data Extracted

- **Solution:** Adjust the system prompt in configuration
- **Solution:** Use more consistent formatting in PDFs
- **Solution:** Test extraction with debug logging enabled

### Missing Timestamps

- **Solution:** Include explicit dates/times in PDF
- **Solution:** System will use current time if no timestamp found
