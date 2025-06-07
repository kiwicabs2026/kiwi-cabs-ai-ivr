def parse_booking_speech(speech_text):
    """Parse booking details from speech input including NZ date format"""
    booking_data = {
        'name': '',
        'pickup_address': '',
        'destination': '',
        'pickup_time': '',
        'pickup_date': '',
        'raw_speech': speech_text
    }
    
    # Extract name - IMPROVED patterns that exclude street names
    name_patterns = [
        # Handle possessive forms like "Saddam Hussein's"
        r"^([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)'s\s+from",
        # Standard introduction patterns
        r"(?:my name is|i am|this is|it's)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)",
        # Names at start of sentence, but NOT followed by street types
        r"^([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)\b(?!\s+(?:Street|Road|Avenue|Lane|Drive|Crescent|Way|Boulevard|Terrace))",
        # Names before "from" but not street names
        r"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)\b(?!\s+(?:Street|Road|Avenue|Lane|Drive))\s+from",
    ]
    
    for pattern in name_patterns:
        match = re.search(pattern, speech_text, re.IGNORECASE)
        if match:
            potential_name = match.group(1).strip()
            # Filter out common non-name words and street names
            if not any(word in potential_name.lower() for word in [
                'need', 'want', 'going', 'from', 'taxi', 'booking', 
                'street', 'road', 'avenue', 'lane', 'drive', 'crescent', 
                'way', 'boulevard', 'terrace', 'hobart', 'willis', 'cuba'
            ]):
                booking_data['name'] = potential_name
                break
    
    # Extract pickup address - IMPROVED with proper address patterns
    pickup_patterns = [
        # Match number + street name + street type
        r"from\s+(\d+\s+[A-Z][a-z]+(?:\s+(?:Street|Road|Avenue|Lane|Drive|Crescent|Way|Boulevard|Terrace)))",
        # Fallback patterns
        r"(?:from|pick up from|pickup from)\s+([^,]+?)(?:\s+(?:to|going|I'm|and))",
        r"(?:from|pick up from|pickup from)\s+([^,]+)$"
    ]
    
    for pattern in pickup_patterns:
        match = re.search(pattern, speech_text, re.IGNORECASE)
        if match:
            pickup = match.group(1).strip()
            # Simple cleanup
            pickup = pickup.replace(" I'm", "").replace(" and", "")
            
            # Fix common speech recognition errors for Wellington streets
            pickup = pickup.replace("63rd Street Melbourne", "63 Hobart Street")
            pickup = pickup.replace("Melbourne Street", "Hobart Street")
            pickup = pickup.replace("mill street", "Willis Street")
            pickup = pickup.replace("labor key", "Lambton Quay")
            
            booking_data['pickup_address'] = pickup
            break
    
    # Extract destination - FIXED to handle "number" prefix and common patterns
    destination_patterns = [
        # Handle "going to number X" pattern specifically
        r"(?:to|going to|going)\s+number\s+(\d+\s+[^,]+?)(?:\s+(?:tomorrow|today|tonight|at|\d{1,2}:|on|date|right now|now))",
        # Standard patterns without "number"
        r"(?:to|going to|going)\s+([^,]+?)(?:\s+(?:tomorrow|today|tonight|at|\d{1,2}:|on|date|right now|now))",
        # End of line patterns
        r"(?:to|going to|going)\s+number\s+(\d+\s+.+)$",
        r"(?:to|going to|going)\s+(.+)$"
    ]
    
    for pattern in destination_patterns:
        match = re.search(pattern, speech_text, re.IGNORECASE)
        if match:
            destination = match.group(1).strip()
            
            # Clean up common issues
            destination = destination.replace("wellington wellington", "wellington")
            # Remove trailing time indicators that might have been captured
            destination = re.sub(r'\s+(at|around|by)\s+\d+', '', destination)
            # Clean up "te aro" if it got split
            destination = re.sub(r'\s+te\s+aro', ', Te Aro', destination, flags=re.IGNORECASE)
            
            # Smart destination mapping - comprehensive airport detection
            if "hospital" in destination.lower():
                destination = "Wellington Hospital"
            elif any(airport_word in destination.lower() for airport_word in [
                "airport", "the airport", "domestic airport", "international airport", 
                "steward duff", "stewart duff", "steward duff driver airport", 
                "stewart duff driver airport", "wlg airport", "wellington airport"
            ]):
                destination = "Wellington Airport"
            elif "station" in destination.lower() or "railway" in destination.lower():
                destination = "Wellington Railway Station"
            elif "te papa" in destination.lower():
                destination = "Te Papa Museum"
            elif "cbd" in destination.lower() or "city centre" in destination.lower():
                destination = "Wellington CBD"
            
            booking_data['destination'] = destination
            break
    
    # Extract date - intelligent parsing for natural language
    from datetime import datetime, timedelta
    
    # RIGHT NOW / ASAP keywords = current date and immediate time
    immediate_keywords = ["right now", "now", "asap", "as soon as possible", "immediately", "straight away"]
    
    # AFTER TOMORROW keywords = day after tomorrow (+2 days)
    after_tomorrow_keywords = ["after tomorrow", "day after tomorrow", "the day after tomorrow"]
    
    # TOMORROW keywords = next day (+1 day)
    tomorrow_keywords = ["tomorrow morning", "tomorrow afternoon", "tomorrow evening", "tomorrow night", "tomorrow"]
    
    # TODAY keywords = current date (same day)
    today_keywords = ["tonight", "today", "later today", "this afternoon", 
                      "this evening", "this morning"]
    
    # Smart parsing - check for immediate requests first
    if any(keyword in speech_text.lower() for keyword in immediate_keywords):
        current_time = datetime.now()
        booking_data['pickup_date'] = current_time.strftime("%d/%m/%Y")
        booking_data['pickup_time'] = "ASAP"
        print(f"🚨 IMMEDIATE BOOKING DETECTED: Setting to TODAY ASAP")
    elif any(keyword in speech_text.lower() for keyword in after_tomorrow_keywords):
        day_after_tomorrow = datetime.now() + timedelta(days=2)
        booking_data['pickup_date'] = day_after_tomorrow.strftime("%d/%m/%Y")
    elif any(keyword in speech_text.lower() for keyword in tomorrow_keywords):
        tomorrow = datetime.now() + timedelta(days=1)
        booking_data['pickup_date'] = tomorrow.strftime("%d/%m/%Y")
    elif any(keyword in speech_text.lower() for keyword in today_keywords):
        today = datetime.now()
        booking_data['pickup_date'] = today.strftime("%d/%m/%Y")
    else:
        # Try to find explicit date formats
        date_patterns = [
            r"(?:date|on)\s+(\d{1,2}/\d{1,2}/\d{4})",
            r"(?:date|on)\s+(\d{1,2}/\d{1,2}/\d{2})",
            r"(\d{1,2}/\d{1,2}/\d{4})",
            r"(\d{1,2}/\d{1,2}/\d{2})"
        ]
        
        for pattern in date_patterns:
            match = re.search(pattern, speech_text, re.IGNORECASE)
            if match:
                booking_data['pickup_date'] = match.group(1).strip()
                break
    
    # Extract time - improved patterns including immediate requests
    time_patterns = [
        r"time\s+(\d{1,2}:?\d{0,2}\s*(?:am|pm|a\.?m\.?|p\.?m\.?))",
        r"at\s+(\d{1,2}:?\d{0,2}\s*(?:am|pm|a\.?m\.?|p\.?m\.?))",
        r"at\s+(quarter\s+past\s+\d{1,2}\s*(?:am|pm|a\.?m\.?|p\.?m\.?))",
        r"at\s+(half\s+past\s+\d{1,2}\s*(?:am|pm|a\.?m\.?|p\.?m\.?))",
        r"(?:today|tomorrow|tonight)\s+at\s+(\d{1,2}:?\d{0,2}\s*(?:am|pm|a\.?m\.?|p\.?m\.?))",
        r"(\d{1,2}:?\d{0,2}\s*(?:am|pm|a\.?m\.?|p\.?m\.?))"
    ]
    
    # Check for immediate time requests first (overrides specific times)
    immediate_time_keywords = ["right now", "now", "asap", "as soon as possible", "immediately", "straight away"]
    
    if any(keyword in speech_text.lower() for keyword in immediate_time_keywords):
        booking_data['pickup_time'] = "ASAP"
        print(f"🚨 IMMEDIATE TIME DETECTED: Setting to ASAP")
    else:
        # Look for specific times
        for pattern in time_patterns:
            match = re.search(pattern, speech_text, re.IGNORECASE)
            if match:
                time_str = match.group(1).strip()
                # Convert quarter past, half past
                if "quarter past" in time_str:
                    time_str = time_str.replace("quarter past ", "").replace("quarter past", "")
                    hour = time_str.split()[0]
                    ampm = time_str.split()[-1] if len(time_str.split()) > 1 else ""
                    time_str = f"{hour}:15 {ampm}"
                elif "half past" in time_str:
                    time_str = time_str.replace("half past ", "").replace("half past", "")
                    hour = time_str.split()[0]
                    ampm = time_str.split()[-1] if len(time_str.split()) > 1 else ""
                    time_str = f"{hour}:30 {ampm}"
                
                # Fix formatting for times like "9 p.m."
                time_str = time_str.replace('p.m.', 'PM').replace('p.m', 'PM')
                time_str = time_str.replace('a.m.', 'AM').replace('a.m', 'AM')
                
                # Add :00 if no minutes specified
                if ':' not in time_str and any(x in time_str for x in ['AM', 'PM']):
                    time_str = time_str.replace(' AM', ':00 AM').replace(' PM', ':00 PM')
                
                booking_data['pickup_time'] = time_str
                break
    
    return booking_data