# Reservation App API

A Flask-based reservation API compatible with Vapi custom tools. This app allows you to reserve any time slot and stores entries in a SQLite database.

## Features

- Create reservations for any time slot
- Check availability for time slots
- List all reservations (with optional date filtering)
- Cancel reservations
- Vapi-compatible webhook endpoint
- Direct REST API endpoints

## Setup

### Local Development

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Run the app:
```bash
python app.py
```

The app will start on `http://localhost:5000`

### Railway Deployment

This app is configured for deployment on Railway. The necessary files are included:

- `Procfile` - Tells Railway how to run the app
- `runtime.txt` - Specifies Python version
- `.gitignore` - Excludes database and cache files from git

To deploy:

1. Create a new Railway project
2. Connect your Git repository
3. Railway will automatically detect the Flask app and deploy it
4. The app will be available at your Railway-provided URL

The app automatically uses the `PORT` environment variable that Railway provides.

## API Endpoints

### Vapi Webhook Endpoint

**POST /webhook**

This is the main endpoint for Vapi tool calls. It expects requests in Vapi's format and returns responses in the required format.

#### Supported Functions

1. **create_reservation**
   - Parameters:
     - `start_time` (required): ISO 8601 datetime string (e.g., "2024-01-15T10:00:00Z")
     - `end_time` (required): ISO 8601 datetime string
     - `description` (optional): Description of the reservation
   - Returns: Confirmation message with reservation ID

2. **check_availability**
   - Parameters:
     - `start_time` (required): ISO 8601 datetime string
     - `end_time` (required): ISO 8601 datetime string
   - Returns: JSON object with `available` boolean and `conflicts` array if unavailable

3. **list_reservations**
   - Parameters:
     - `start_date` (optional): Filter reservations from this date
     - `end_date` (optional): Filter reservations until this date
   - Returns: JSON object with `reservations` array and `count`

4. **cancel_reservation**
   - Parameters:
     - `id` (optional): Reservation ID to cancel
     - OR `start_time` + `end_time` (optional): Time slot to cancel
   - Returns: Confirmation message

### Direct REST Endpoints

**GET /health**
- Health check endpoint
- Returns: `{"status": "healthy"}`

**GET /reservations**
- Get all reservations
- Returns: JSON object with all reservations

## Vapi Tool Schema Examples

### create_reservation
```json
{
  "name": "create_reservation",
  "description": "Create a new reservation for a time slot",
  "parameters": {
    "type": "object",
    "properties": {
      "start_time": {
        "type": "string",
        "description": "Start time in ISO 8601 format (e.g., 2024-01-15T10:00:00Z)"
      },
      "end_time": {
        "type": "string",
        "description": "End time in ISO 8601 format (e.g., 2024-01-15T11:00:00Z)"
      },
      "description": {
        "type": "string",
        "description": "Optional description of the reservation"
      }
    },
    "required": ["start_time", "end_time"]
  },
  "strict": true,
  "maxTokens": 500
}
```

### check_availability
```json
{
  "name": "check_availability",
  "description": "Check if a time slot is available for reservation",
  "parameters": {
    "type": "object",
    "properties": {
      "start_time": {
        "type": "string",
        "description": "Start time in ISO 8601 format"
      },
      "end_time": {
        "type": "string",
        "description": "End time in ISO 8601 format"
      }
    },
    "required": ["start_time", "end_time"]
  },
  "strict": true,
  "maxTokens": 500
}
```

### list_reservations
```json
{
  "name": "list_reservations",
  "description": "List all reservations, optionally filtered by date range",
  "parameters": {
    "type": "object",
    "properties": {
      "start_date": {
        "type": "string",
        "description": "Optional start date filter in ISO 8601 format"
      },
      "end_date": {
        "type": "string",
        "description": "Optional end date filter in ISO 8601 format"
      }
    },
    "required": []
  },
  "strict": true,
  "maxTokens": 1000
}
```

### cancel_reservation
```json
{
  "name": "cancel_reservation",
  "description": "Cancel a reservation by ID or time slot",
  "parameters": {
    "type": "object",
    "properties": {
      "id": {
        "type": "integer",
        "description": "Reservation ID to cancel"
      },
      "start_time": {
        "type": "string",
        "description": "Start time of reservation to cancel (must provide with end_time)"
      },
      "end_time": {
        "type": "string",
        "description": "End time of reservation to cancel (must provide with start_time)"
      }
    },
    "required": []
  },
  "strict": true,
  "maxTokens": 500
}
```

## Database

The app uses SQLite with a `reservations` table containing:
- `id`: Auto-incrementing primary key
- `start_time`: Reservation start time (ISO 8601 string)
- `end_time`: Reservation end time (ISO 8601 string)
- `description`: Optional description
- `created_at`: Timestamp when reservation was created

The database file `reservations.db` is created automatically on first run.

## Vapi Compatibility

The webhook endpoint follows Vapi's requirements:
- Returns HTTP 200 for all responses (even errors)
- Returns results as single-line strings (JSON is stringified)
- Matches tool call IDs exactly
- Handles multiple tool calls in parallel
- Uses proper error format in results array

## Example Usage

### Create a reservation via Vapi webhook:
```json
POST /webhook
{
  "calls": [
    {
      "toolCallId": "call_123",
      "function": {
        "name": "create_reservation",
        "arguments": {
          "start_time": "2024-01-15T10:00:00Z",
          "end_time": "2024-01-15T11:00:00Z",
          "description": "Meeting with client"
        }
      }
    }
  ]
}
```

### Response:
```json
{
  "results": [
    {
      "toolCallId": "call_123",
      "result": "Reservation created successfully. ID: 1, Start: 2024-01-15T10:00:00Z, End: 2024-01-15T11:00:00Z"
    }
  ]
}
```

