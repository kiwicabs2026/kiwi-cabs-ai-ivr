from flask import Flask, request, jsonify
from datetime import datetime, timedelta
import json
import random
import string
import re

app = Flask(__name__)

# In-memory storage (replace with database in production)
bookings = {}
user_sessions = {}
pending_bookings = {}

# Helper functions
def generate_booking_id():
    """Generate a unique booking ID"""
    return 'KC' + ''.join(random.choices(string.digits, k=6))

def estimate_fare(pickup, destination):
    """Estimate fare based on locations"""
    base_fare = 10
    per_km = 2.5
    estimated_distance = random.randint(5, 20)  # Mock distance
    return base_fare + (per_km * estimated_distance), estimated_distance

def validate_location(location):
    """Validate if location is valid"""
    # Basic validation - in production, integrate with maps API
    return len(location) >= 3

def parse_time_input(time_input):
    """Parse time input and return formatted time"""
    time_lower = time_input.lower()
    
    if 'now' in time_lower or 'asap' in time_lower:
        return 'Now', datetime.now()
    elif '30 min' in time_lower or 'half hour' in time_lower:
        return 'In 30 minutes', datetime.now() + timedelta(minutes=30)
    elif '1 hour' in time_lower or 'one hour' in time_lower:
        return 'In 1 hour', datetime.now() + timedelta(hours=1)
    else:
        # Try to parse custom time - simplified for demo
        return time_input, datetime.now()  # In production, parse actual time

def assign_driver():
    """Assign a mock driver"""
    drivers = [
        {'name': 'John Smith', 'rating': 4.8},
        {'name': 'Sarah Johnson', 'rating': 4.9},
        {'name': 'Mike Brown', 'rating': 4.7},
        {'name': 'Emma Davis', 'rating': 4.9}
    ]
    
    driver = random.choice(drivers)
    driver.update({
        'phone': '+64 21 ' + ''.join(random.choices(string.digits, k=7)),
        'vehicle': random.choice(['Toyota Prius', 'Honda Accord', 'Tesla Model 3', 'Nissan Leaf']),
        'plate': ''.join(random.choices(string.ascii_uppercase, k=3)) + ''.join(random.choices(string.digits, k=3)),
        'eta': random.randint(5, 15)
    })
    
    return driver

# Webhook endpoints for Twilio Studio

@app.route("/validate_pickup", methods=['POST'])
def validate_pickup():
    """Validate pickup location from Studio flow"""
    data = request.get_json() or request.form
    pickup = data.get('pickup', '').strip()
    phone = data.get('From', '')
    
    if not pickup:
        return jsonify({
            'valid': False,
            'message': 'Please provide a pickup location.'
        })
    
    if not validate_location(pickup):
        return jsonify({
            'valid': False,
            'message': 'Please enter a valid pickup location with at least 3 characters.'
        })
    
    # Store in session
    if phone not in user_sessions:
        user_sessions[phone] = {}
    user_sessions[phone]['pickup'] = pickup
    
    return jsonify({
        'valid': True,
        'pickup': pickup,
        'message': f'Pickup location set to: {pickup}'
    })

@app.route("/validate_destination", methods=['POST'])
def validate_destination():
    """Validate destination from Studio flow"""
    data = request.get_json() or request.form
    destination = data.get('destination', '').strip()
    phone = data.get('From', '')
    
    if not destination:
        return jsonify({
            'valid': False,
            'message': 'Please provide a destination.'
        })
    
    if not validate_location(destination):
        return jsonify({
            'valid': False,
            'message': 'Please enter a valid destination with at least 3 characters.'
        })
    
    # Store in session
    if phone not in user_sessions:
        user_sessions[phone] = {}
    user_sessions[phone]['destination'] = destination
    
    return jsonify({
        'valid': True,
        'destination': destination,
        'message': f'Destination set to: {destination}'
    })

@app.route("/process_time", methods=['POST'])
def process_time():
    """Process time selection from Studio flow"""
    data = request.get_json() or request.form
    time_input = data.get('time', '').strip()
    phone = data.get('From', '')
    
    if not time_input:
        return jsonify({
            'valid': False,
            'message': 'Please specify when you want to travel.'
        })
    
    time_display, pickup_time = parse_time_input(time_input)
    
    # Store in session
    if phone not in user_sessions:
        user_sessions[phone] = {}
    user_sessions[phone]['time'] = time_display
    user_sessions[phone]['pickup_time'] = pickup_time.isoformat()
    
    return jsonify({
        'valid': True,
        'time': time_display,
        'message': f'Pickup time set to: {time_display}'
    })

@app.route("/calculate_fare", methods=['POST'])
def calculate_fare():
    """Calculate fare and prepare booking summary"""
    data = request.get_json() or request.form
    phone = data.get('From', '')
    
    if phone not in user_sessions:
        return jsonify({
            'success': False,
            'message': 'Session expired. Please start a new booking.'
        })
    
    session = user_sessions[phone]
    
    if 'pickup' not in session or 'destination' not in session:
        return jsonify({
            'success': False,
            'message': 'Missing pickup or destination information.'
        })
    
    # Calculate fare
    fare, distance = estimate_fare(session['pickup'], session['destination'])
    
    # Create pending booking
    booking_data = {
        'pickup': session['pickup'],
        'destination': session['destination'],
        'time': session.get('time', 'Now'),
        'pickup_time': session.get('pickup_time', datetime.now().isoformat()),
        'fare': fare,
        'distance': distance,
        'phone': phone
    }
    
    pending_bookings[phone] = booking_data
    
    # Format summary
    summary = f"""📋 Booking Summary:
    
📍 From: {booking_data['pickup']}
📍 To: {booking_data['destination']}
🕐 Time: {booking_data['time']}
💰 Estimated Fare: ${fare:.2f}
📏 Distance: ~{distance} km

Reply YES to confirm or NO to cancel."""
    
    return jsonify({
        'success': True,
        'summary': summary,
        'fare': fare,
        'distance': distance
    })

@app.route("/confirm_booking", methods=['POST'])
def confirm_booking():
    """Confirm the booking"""
    data = request.get_json() or request.form
    phone = data.get('From', '')
    confirmation = data.get('confirmation', '').lower()
    
    if phone not in pending_bookings:
        return jsonify({
            'success': False,
            'message': 'No pending booking found. Please start a new booking.'
        })
    
    if confirmation not in ['yes', 'y', 'confirm']:
        # Clear pending booking
        del pending_bookings[phone]
        if phone in user_sessions:
            del user_sessions[phone]
        
        return jsonify({
            'success': False,
            'message': 'Booking cancelled. Type "book" to start a new booking.'
        })
    
    # Create confirmed booking
    booking_data = pending_bookings[phone]
    booking_id = generate_booking_id()
    driver = assign_driver()
    
    booking = {
        'id': booking_id,
        'user_phone': phone,
        'pickup': booking_data['pickup'],
        'destination': booking_data['destination'],
        'time': booking_data['time'],
        'pickup_time': booking_data['pickup_time'],
        'fare': booking_data['fare'],
        'distance': booking_data['distance'],
        'driver': driver,
        'status': 'Confirmed',
        'created_at': datetime.now().isoformat()
    }
    
    bookings[booking_id] = booking
    
    # Clear session data
    del pending_bookings[phone]
    if phone in user_sessions:
        del user_sessions[phone]
    
    # Format confirmation message
    confirmation_msg = f"""🎉 Booking Confirmed!

📋 Booking ID: {booking_id}
🚗 Driver: {driver['name']} (⭐ {driver['rating']})
🚙 Vehicle: {driver['vehicle']} - {driver['plate']}
📱 Driver Contact: {driver['phone']}
⏱️ ETA: {driver['eta']} minutes

Your driver is on the way! You'll receive updates via SMS."""
    
    return jsonify({
        'success': True,
        'booking_id': booking_id,
        'message': confirmation_msg,
        'driver_name': driver['name'],
        'driver_phone': driver['phone'],
        'eta': driver['eta']
    })

@app.route("/check_status", methods=['POST'])
def check_status():
    """Check booking status"""
    data = request.get_json() or request.form
    booking_id = data.get('booking_id', '').strip().upper()
    
    if not booking_id:
        return jsonify({
            'success': False,
            'message': 'Please provide a booking ID.'
        })
    
    if booking_id not in bookings:
        return jsonify({
            'success': False,
            'message': f'No booking found with ID {booking_id}.'
        })
    
    booking = bookings[booking_id]
    
    status_msg = f"""📋 Booking Status:

Booking ID: {booking_id}
Status: {booking['status']}
Driver: {booking['driver']['name']}
Vehicle: {booking['driver']['vehicle']}
ETA: {booking['driver']['eta']} minutes
Pickup: {booking['pickup']}
Destination: {booking['destination']}"""
    
    return jsonify({
        'success': True,
        'status': booking['status'],
        'message': status_msg
    })

@app.route("/cancel_booking", methods=['POST'])
def cancel_booking():
    """Cancel a booking"""
    data = request.get_json() or request.form
    booking_id = data.get('booking_id', '').strip().upper()
    phone = data.get('From', '')
    
    if not booking_id:
        return jsonify({
            'success': False,
            'message': 'Please provide a booking ID to cancel.'
        })
    
    if booking_id not in bookings:
        return jsonify({
            'success': False,
            'message': f'No booking found with ID {booking_id}.'
        })
    
    booking = bookings[booking_id]
    
    # Verify ownership
    if booking['user_phone'] != phone:
        return jsonify({
            'success': False,
            'message': 'You can only cancel your own bookings.'
        })
    
    # Cancel the booking
    booking['status'] = 'Cancelled'
    
    return jsonify({
        'success': True,
        'message': f'Booking {booking_id} has been cancelled successfully.'
    })

@app.route("/handle_fallback", methods=['POST'])
def handle_fallback():
    """Handle fallback for unrecognized inputs"""
    data = request.get_json() or request.form
    user_input = data.get('Body', '').strip()
    
    # Try to understand intent
    user_input_lower = user_input.lower()
    
    if any(word in user_input_lower for word in ['book', 'cab', 'taxi', 'ride']):
        message = "To book a cab, please type 'book' to start the booking process."
    elif any(word in user_input_lower for word in ['status', 'where', 'driver']):
        message = "To check your booking status, type 'status' followed by your booking ID (e.g., 'status KC123456')."
    elif any(word in user_input_lower for word in ['cancel', 'stop']):
        message = "To cancel a booking, type 'cancel' followed by your booking ID (e.g., 'cancel KC123456')."
    else:
        message = """I can help you with:
• Book a cab - Type 'book'
• Check status - Type 'status [booking ID]'
• Cancel booking - Type 'cancel [booking ID]'

What would you like to do?"""
    
    return jsonify({
        'message': message
    })

@app.route("/health", methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'service': 'Kiwi Cabs Booking Service',
        'version': '2.0'
    }), 200

if __name__ == '__main__':
    app.run(debug=True, port=5000)