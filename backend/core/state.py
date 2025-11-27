"""
Core State Management Module
Handles processing state storage and management (RAM-only)
"""

import threading
import hashlib
import queue as queue_module

# ============================================================================
# GLOBAL STATE STORAGE
# ============================================================================

# Global lock for thread-safe operations
processing_lock = threading.RLock()

# Global in-memory storage for processing states
# Structure: {doc_id: {state_data}}
processing_states_memory = {}

# SSE listeners for real-time updates
processing_listeners = set()

print("💾 RAM-ONLY MODE: Processing states will be stored in memory only")

# ============================================================================
# STATE MANAGEMENT FUNCTIONS
# ============================================================================

def generate_document_id(company_id: str, file_name: str) -> str:
    """
    Generate a unique document ID based on company name and file name (deterministic)
    
    Args:
        company_id: Company identifier
        file_name: File name
        
    Returns:
        16-character hex document ID
    """
    combined = f"{company_id}:{file_name}"
    return hashlib.sha1(combined.encode()).hexdigest()[:16]


def load_processing_states(company_id: str) -> dict:
    """
    Load processing states from in-memory storage for a specific company.
    Returns all document states that belong to this company.
    
    Args:
        company_id: Company identifier
        
    Returns:
        Dictionary of {doc_id: state_data}
    """
    with processing_lock:
        # Filter states by company_id
        company_states = {
            doc_id: state.copy()  # Return copy to prevent external modification
            for doc_id, state in processing_states_memory.items()
            if state.get('company_id') == company_id
        }
        return company_states


def save_processing_states(company_id: str, states: dict):
    """
    Save processing states to in-memory storage (RAM only).
    Also broadcasts updates to all SSE listeners.
    
    Args:
        company_id: The company identifier
        states: Dictionary of {doc_id: state_data}
    """
    with processing_lock:
        # Update in-memory storage
        for doc_id, state in states.items():
            # Ensure company_id is set
            if 'company_id' not in state:
                state['company_id'] = company_id
            processing_states_memory[doc_id] = state
        
        # Notify listeners of update via SSE
        notify_processing_update({"type": "states_updated", "states": states})


def cleanup_processing_state(doc_id: str) -> dict:
    """
    Remove a processing state from memory when processing is complete.
    Called after a document finishes processing.
    
    Args:
        doc_id: The document identifier to remove
        
    Returns:
        The removed state, or None if not found
    """
    with processing_lock:
        removed = processing_states_memory.pop(doc_id, None)
        if removed:
            print(f"🗑️  CLEANED UP: {doc_id} | Memory freed")
        return removed


def notify_processing_update(data: dict):
    """
    Notify all SSE listeners of a processing update
    
    Args:
        data: Update data to broadcast
    """
    import json
    
    with processing_lock:
        # Create a copy of the listeners set to avoid modification during iteration
        listeners = processing_listeners.copy()

    # Send update to all listeners
    disconnected = set()
    for listener_queue in listeners:
        try:
            listener_queue.put(json.dumps(data))
        except:
            disconnected.add(listener_queue)

    # Remove disconnected listeners
    if disconnected:
        with processing_lock:
            processing_listeners.difference_update(disconnected)


def get_all_processing_states() -> dict:
    """
    Get all processing states from memory
    
    Returns:
        Dictionary of all processing states
    """
    with processing_lock:
        return processing_states_memory.copy()

print("✅ State management initialized")
