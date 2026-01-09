from flask import Flask, request, jsonify
from datetime import datetime
import psycopg2
from psycopg2.extras import RealDictCursor
import json
import os

app = Flask(__name__)

# Get database URL from environment (Railway provides DATABASE_URL)
DATABASE_URL = os.environ.get('DATABASE_URL')

def get_db_connection():
    """Get database connection"""
    if not DATABASE_URL:
        raise Exception("DATABASE_URL environment variable is not set")
    
    conn = psycopg2.connect(DATABASE_URL)
    return conn

def init_db():
    """Initialize the database with reservations table"""
    conn = get_db_connection()
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS reservations (
            id SERIAL PRIMARY KEY,
            start_time TEXT NOT NULL,
            end_time TEXT NOT NULL,
            description TEXT,
            created_at TEXT NOT NULL,
            UNIQUE(start_time, end_time)
        )
    ''')
    conn.commit()
    conn.close()

@app.route('/webhook', methods=['POST'])
def webhook():
    """Main webhook endpoint for Vapi tool calls"""
    try:
        data = request.get_json()
        
        if not data or 'calls' not in data:
            return jsonify({"error": "Invalid request format"}), 400
        
        results = []
        
        for call in data.get('calls', []):
            tool_call_id = call.get('toolCallId')
            function_name = call.get('function', {}).get('name')
            parameters = call.get('function', {}).get('arguments', {})
            
            if isinstance(parameters, str):
                try:
                    parameters = json.loads(parameters)
                except json.JSONDecodeError:
                    parameters = {}
            
            # Route to appropriate handler
            if function_name == 'create_reservation':
                result, error = handle_create_reservation(parameters)
            elif function_name == 'check_availability':
                result, error = handle_check_availability(parameters)
            elif function_name == 'list_reservations':
                result, error = handle_list_reservations(parameters)
            elif function_name == 'cancel_reservation':
                result, error = handle_cancel_reservation(parameters)
            else:
                result = None
                error = f"Unknown function: {function_name}"
            
            # Format result as single-line string (Vapi requirement)
            if error:
                # Remove ALL line breaks from error messages
                error_str = str(error).replace('\n', ' ').replace('\r', '')
                results.append({
                    "toolCallId": tool_call_id,
                    "error": error_str
                })
            else:
                # Convert result to single-line string - NO LINE BREAKS
                if isinstance(result, (dict, list)):
                    # Use ensure_ascii=False to handle unicode, but NO indentation/newlines
                    result_str = json.dumps(result, separators=(',', ':'), ensure_ascii=False)
                else:
                    result_str = str(result)
                
                # CRITICAL: Remove ALL line breaks (Vapi requirement)
                result_str = result_str.replace('\n', ' ').replace('\r', '')
                
                results.append({
                    "toolCallId": tool_call_id,
                    "result": result_str
                })
        
        return jsonify({"results": results}), 200
    
    except Exception as e:
        # Even on exception, return 200 with error in results
        error_str = str(e).replace('\n', ' ').replace('\r', '')
        return jsonify({"error": error_str}), 200

def handle_create_reservation(params):
    """Handle reservation creation"""
    conn = None
    try:
        start_time = params.get('start_time')
        end_time = params.get('end_time')
        description = params.get('description', '')
        
        if not start_time or not end_time:
            return None, "start_time and end_time are required"
        
        # Validate datetime format
        try:
            start_dt = datetime.fromisoformat(start_time.replace('Z', '+00:00'))
            end_dt = datetime.fromisoformat(end_time.replace('Z', '+00:00'))
        except ValueError:
            return None, "Invalid datetime format. Use ISO 8601 format (e.g., 2024-01-15T10:00:00Z)"
        
        if end_dt <= start_dt:
            return None, "end_time must be after start_time"
        
        conn = get_db_connection()
        c = conn.cursor(cursor_factory=RealDictCursor)
        
        # Check for conflicts
        c.execute('''
            SELECT * FROM reservations 
            WHERE (start_time < %s AND end_time > %s)
               OR (start_time < %s AND end_time > %s)
               OR (start_time >= %s AND end_time <= %s)
        ''', (end_time, start_time, end_time, start_time, start_time, end_time))
        
        if c.fetchone():
            conn.close()
            return None, "Time slot conflicts with existing reservation"
        
        # Insert reservation
        created_at = datetime.utcnow().isoformat() + 'Z'
        c.execute('''
            INSERT INTO reservations (start_time, end_time, description, created_at)
            VALUES (%s, %s, %s, %s)
            RETURNING id
        ''', (start_time, end_time, description, created_at))
        
        reservation_id = c.fetchone()['id']
        conn.commit()
        conn.close()
        
        # Return single-line string (no line breaks)
        return f"Reservation created successfully. ID: {reservation_id}, Start: {start_time}, End: {end_time}", None
    
    except psycopg2.IntegrityError:
        if conn:
            conn.rollback()
            conn.close()
        return None, "Reservation already exists for this time slot"
    except Exception as e:
        if conn:
            conn.rollback()
            conn.close()
        return None, f"Error creating reservation: {str(e)}"

def handle_check_availability(params):
    """Check if a time slot is available"""
    conn = None
    try:
        start_time = params.get('start_time')
        end_time = params.get('end_time')
        
        if not start_time or not end_time:
            return None, "start_time and end_time are required"
        
        conn = get_db_connection()
        c = conn.cursor(cursor_factory=RealDictCursor)
        
        # Check for conflicts
        c.execute('''
            SELECT * FROM reservations 
            WHERE (start_time < %s AND end_time > %s)
               OR (start_time < %s AND end_time > %s)
               OR (start_time >= %s AND end_time <= %s)
        ''', (end_time, start_time, end_time, start_time, start_time, end_time))
        
        conflicts = c.fetchall()
        conn.close()
        
        if conflicts:
            conflict_list = []
            for conflict in conflicts:
                conflict_list.append({
                    "start_time": conflict['start_time'],
                    "end_time": conflict['end_time'],
                    "description": conflict.get('description', '')
                })
            # Return dict - will be converted to single-line JSON
            return {"available": False, "conflicts": conflict_list}, None
        else:
            return {"available": True}, None
    
    except Exception as e:
        if conn:
            conn.close()
        return None, f"Error checking availability: {str(e)}"

def handle_list_reservations(params):
    """List all reservations, optionally filtered by date range"""
    conn = None
    try:
        start_date = params.get('start_date')
        end_date = params.get('end_date')
        
        conn = get_db_connection()
        c = conn.cursor(cursor_factory=RealDictCursor)
        
        if start_date and end_date:
            c.execute('''
                SELECT * FROM reservations 
                WHERE start_time >= %s AND end_time <= %s
                ORDER BY start_time ASC
            ''', (start_date, end_date))
        else:
            c.execute('''
                SELECT * FROM reservations 
                ORDER BY start_time ASC
            ''')
        
        reservations = c.fetchall()
        conn.close()
        
        result = []
        for res in reservations:
            result.append({
                "id": res['id'],
                "start_time": res['start_time'],
                "end_time": res['end_time'],
                "description": res.get('description', ''),
                "created_at": res['created_at']
            })
        
        # Return dict - will be converted to single-line JSON
        return {"reservations": result, "count": len(result)}, None
    
    except Exception as e:
        if conn:
            conn.close()
        return None, f"Error listing reservations: {str(e)}"

def handle_cancel_reservation(params):
    """Cancel a reservation by ID or time slot"""
    conn = None
    try:
        reservation_id = params.get('id')
        start_time = params.get('start_time')
        end_time = params.get('end_time')
        
        conn = get_db_connection()
        c = conn.cursor(cursor_factory=RealDictCursor)
        
        if reservation_id:
            c.execute('DELETE FROM reservations WHERE id = %s', (reservation_id,))
        elif start_time and end_time:
            c.execute('DELETE FROM reservations WHERE start_time = %s AND end_time = %s', 
                     (start_time, end_time))
        else:
            conn.close()
            return None, "Either 'id' or both 'start_time' and 'end_time' are required"
        
        if c.rowcount == 0:
            conn.close()
            return None, "Reservation not found"
        
        conn.commit()
        conn.close()
        
        return "Reservation cancelled successfully", None
    
    except Exception as e:
        if conn:
            conn.rollback()
            conn.close()
        return None, f"Error cancelling reservation: {str(e)}"

@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint"""
    return jsonify({"status": "healthy"}), 200

@app.route('/reservations', methods=['GET'])
def get_reservations():
    """Direct API endpoint to get all reservations (non-Vapi)"""
    conn = None
    try:
        conn = get_db_connection()
        c = conn.cursor(cursor_factory=RealDictCursor)
        c.execute('SELECT * FROM reservations ORDER BY start_time ASC')
        reservations = c.fetchall()
        conn.close()
        
        result = []
        for res in reservations:
            result.append({
                "id": res['id'],
                "start_time": res['start_time'],
                "end_time": res['end_time'],
                "description": res.get('description', ''),
                "created_at": res['created_at']
            })
        
        return jsonify({"reservations": result, "count": len(result)}), 200
    except Exception as e:
        if conn:
            conn.close()
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    init_db()
    port = int(os.environ.get('PORT', 5000))
    app.run(debug=False, host='0.0.0.0', port=port)
