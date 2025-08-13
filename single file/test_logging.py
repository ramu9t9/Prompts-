import json
from datetime import datetime

def log_ai_interaction(analysis_type, prompt, response, context_data=None):
    """Log AI interactions for debugging and verification."""
    print(f"🔍 DEBUG: Logging {analysis_type} AI interaction...")
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_entry = {
        "timestamp": timestamp,
        "analysis_type": analysis_type,  # "minimal" or "rich"
        "prompt": prompt,
        "full_response": response,
        "context_data": context_data
    }
    
    # Save to JSON file
    filename = f"ai_log_{datetime.now().strftime('%Y%m%d')}.json"
    print(f"🔍 DEBUG: Writing to {filename}")
    try:
        # Read existing logs
        existing_logs = []
        try:
            with open(filename, 'r', encoding='utf-8') as f:
                existing_logs = json.load(f)
                print(f"🔍 DEBUG: Loaded {len(existing_logs)} existing log entries")
        except FileNotFoundError:
            print(f"🔍 DEBUG: No existing log file found, creating new one")
            pass
        
        # Add new log entry
        existing_logs.append(log_entry)
        
        # Write back to file
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(existing_logs, f, indent=2, ensure_ascii=False)
        
        print(f"🔍 DEBUG: Successfully wrote log entry to {filename}")
        
        # Also create a simple text log for quick reading
        txt_filename = f"ai_log_{datetime.now().strftime('%Y%m%d')}.txt"
        print(f"🔍 DEBUG: Writing to {txt_filename}")
        with open(txt_filename, 'a', encoding='utf-8') as f:
            f.write(f"\n{'='*80}\n")
            f.write(f"TIMESTAMP: {timestamp}\n")
            f.write(f"ANALYSIS TYPE: {analysis_type.upper()}\n")
            f.write(f"PROMPT LENGTH: {len(prompt)} characters\n")
            f.write(f"RESPONSE LENGTH: {len(response)} characters\n")
            f.write(f"FULL RESPONSE:\n{response}\n")
            f.write(f"CONTEXT DATA KEYS: {list(context_data.keys()) if context_data else 'None'}\n")
            f.write(f"{'='*80}\n")
        
        print(f"🔍 DEBUG: Successfully wrote text log to {txt_filename}")
            
    except Exception as e:
        print(f"❌ Logging error: {e}")
        import traceback
        traceback.print_exc()

# Test the logging function
if __name__ == "__main__":
    print("Testing logging function...")
    log_ai_interaction("test", "This is a test prompt", "This is a test response", {"test": "data"})
    print("Logging test completed!")
