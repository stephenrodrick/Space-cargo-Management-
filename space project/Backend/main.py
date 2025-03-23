import os
import json
import time
import heapq
from datetime import datetime, timedelta
from flask import Flask, request, jsonify
from typing import Dict, List, Tuple, Any, Optional

app = Flask(__name__)

# Configuration
DATA_FILE = "cargo_data.json"
LOG_FILE = "cargo_logs.json"

# Data Structure
# {
#   "items": {
#     "item_id": {
#       "name": "Item Name",
#       "location": "container_id",
#       "priority": 1-5,
#       "expiration_date": "YYYY-MM-DD",
#       "volume": float,
#       "weight": float,
#       "category": "food/medical/scientific/waste/etc",
#       "status": "active/used/expired",
#       "arrival_date": "YYYY-MM-DD",
#       "last_accessed": "YYYY-MM-DD HH:MM:SS"
#     }
#   },
#   "containers": {
#     "container_id": {
#       "name": "Container Name",
#       "total_volume": float,
#       "used_volume": float,
#       "max_weight": float,
#       "current_weight": float,
#       "items": ["item_id1", "item_id2"],
#       "type": "storage/waste/return",
#       "accessibility_factor": float (0-1, how easy to access)
#     }
#   },
#   "waste_containers": {
#     "waste_container_id": {
#       "name": "Waste Container Name",
#       "total_volume": float,
#       "used_volume": float,
#       "max_weight": float,
#       "current_weight": float,
#       "waste_categories": ["organic", "plastic", "electronic", "etc"],
#       "undock_date": "YYYY-MM-DD"
#     }
#   }
# }

def load_data() -> Dict:
    """Load cargo data from file"""
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, 'r') as f:
            return json.load(f)
    return {
        "items": {},
        "containers": {},
        "waste_containers": {}
    }

def save_data(data: Dict) -> None:
    """Save cargo data to file"""
    with open(DATA_FILE, 'w') as f:
        json.dump(data, f, indent=2)

def log_action(action: str, details: Dict) -> None:
    """Log astronaut actions"""
    log_entry = {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "action": action,
        "details": details
    }
    
    # Load existing logs
    logs = []
    if os.path.exists(LOG_FILE):
        with open(LOG_FILE, 'r') as f:
            logs = json.load(f)
    
    logs.append(log_entry)
    
    # Save updated logs
    with open(LOG_FILE, 'w') as f:
        json.dump(logs, f, indent=2)
    
    return log_entry

# Feature 1: Efficient Placement of Items
@app.route('/api/place_item', methods=['POST'])
def place_item():
    """Suggest and place new items based on space availability, priority, and accessibility"""
    data = load_data()
    item_data = request.json
    
    if not item_data or 'item_id' not in item_data:
        return jsonify({"error": "Invalid item data"}), 400
    
    # Assign a new ID if not provided
    item_id = item_data.get('item_id', f"item_{int(time.time())}")
    
    # Check if container is specified
    specified_container = item_data.get('container_id')
    
    if specified_container:
        # Check if container exists and has space
        if specified_container not in data['containers']:
            return jsonify({"error": f"Container {specified_container} not found"}), 404
        
        container = data['containers'][specified_container]
        
        # Check space availability
        if container['used_volume'] + item_data['volume'] > container['total_volume']:
            return jsonify({"error": f"Not enough space in container {specified_container}"}), 400
        
        if container['current_weight'] + item_data['weight'] > container['max_weight']:
            return jsonify({"error": f"Weight limit exceeded in container {specified_container}"}), 400
        
        # Place the item
        data['items'][item_id] = {
            "name": item_data['name'],
            "location": specified_container,
            "priority": item_data.get('priority', 3),  # Default priority is 3 (medium)
            "expiration_date": item_data.get('expiration_date'),
            "volume": item_data['volume'],
            "weight": item_data['weight'],
            "category": item_data.get('category', 'general'),
            "status": "active",
            "arrival_date": datetime.now().strftime("%Y-%m-%d"),
            "last_accessed": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        
        # Update container
        data['containers'][specified_container]['used_volume'] += item_data['volume']
        data['containers'][specified_container]['current_weight'] += item_data['weight']
        data['containers'][specified_container]['items'].append(item_id)
        
    else:
        # Find the best container using algorithm
        best_container = find_best_container_for_item(data, item_data)
        
        if not best_container:
            # If no suitable container found, suggest rearrangement
            rearrangement_plan = suggest_rearrangement(data, item_data)
            if rearrangement_plan:
                return jsonify({
                    "status": "rearrangement_needed",
                    "message": "Rearrangement needed to accommodate this item",
                    "rearrangement_plan": rearrangement_plan
                }), 200
            else:
                return jsonify({"error": "No space available for this item, and rearrangement not possible"}), 400
        
        # Place the item in the best container
        data['items'][item_id] = {
            "name": item_data['name'],
            "location": best_container,
            "priority": item_data.get('priority', 3),
            "expiration_date": item_data.get('expiration_date'),
            "volume": item_data['volume'],
            "weight": item_data['weight'],
            "category": item_data.get('category', 'general'),
            "status": "active",
            "arrival_date": datetime.now().strftime("%Y-%m-%d"),
            "last_accessed": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        
        # Update container
        data['containers'][best_container]['used_volume'] += item_data['volume']
        data['containers'][best_container]['current_weight'] += item_data['weight']
        data['containers'][best_container]['items'].append(item_id)
    
    save_data(data)
    
    # Log the action
    log_action("place_item", {
        "item_id": item_id,
        "container_id": specified_container or best_container,
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    })
    
    return jsonify({
        "status": "success",
        "message": f"Item {item_id} placed in container {specified_container or best_container}",
        "item_id": item_id,
        "container_id": specified_container or best_container
    }), 201

def find_best_container_for_item(data: Dict, item_data: Dict) -> Optional[str]:
    """Algorithm to find the best container for a new item"""
    item_volume = item_data['volume']
    item_weight = item_data['weight']
    item_priority = item_data.get('priority', 3)
    
    # Create a score for each container
    container_scores = []
    
    for container_id, container in data['containers'].items():
        # Skip waste and return containers
        if container['type'] not in ['storage']:
            continue
            
        # Skip containers that don't have enough space or weight capacity
        if container['used_volume'] + item_volume > container['total_volume']:
            continue
            
        if container['current_weight'] + item_weight > container['max_weight']:
            continue
        
        # Calculate score based on:
        # 1. Space efficiency (how well the item fits)
        # 2. Accessibility factor
        # 3. Priority alignment (match high priority items with accessible containers)
        
        # Space efficiency: containers with just enough space get higher scores
        remaining_space = container['total_volume'] - container['used_volume']
        space_efficiency = 1 - (remaining_space - item_volume) / container['total_volume']
        
        # Accessibility is important for high priority items
        # High priority (5) items should go in more accessible containers
        accessibility_score = container['accessibility_factor'] * (item_priority / 5)
        
        # Combine scores (adjust weights as needed)
        total_score = (space_efficiency * 0.5) + (accessibility_score * 0.5)
        
        heapq.heappush(container_scores, (-total_score, container_id))  # Negative for max-heap
    
    # Return the best container or None if no suitable container
    return container_scores[0][1] if container_scores else None

# Feature 2: Quick Retrieval of Items
@app.route('/api/find_item', methods=['GET'])
def find_item():
    """Find items based on search criteria and suggest fastest retrieval order"""
    data = load_data()
    search_query = request.args.get('query', '').lower()
    category = request.args.get('category')
    
    # Find matching items
    matching_items = []
    
    for item_id, item in data['items'].items():
        if item['status'] != 'active':
            continue
            
        if (search_query in item['name'].lower() or search_query in item_id.lower()) and \
           (not category or item['category'] == category):
            # Get container info for accessibility calculation
            container = data['containers'][item['location']]
            
            # Calculate retrieval score based on:
            # 1. Accessibility of container
            # 2. Position in container (approximated by when it was added)
            # 3. Priority of item
            # 4. Expiration date (items closer to expiry get priority)
            
            # Basic retrieval time based on accessibility
            retrieval_time = (1 - container['accessibility_factor']) * 10  # 0-10 minutes
            
            # Adjust for position in container (more recent items are easier to access)
            item_index = container['items'].index(item_id)
            position_factor = item_index / max(1, len(container['items']))
            retrieval_time += position_factor * 5  # Add 0-5 minutes based on position
            
            # Store item with its retrieval information
            item_info = {
                "item_id": item_id,
                "name": item['name'],
                "location": item['location'],
                "container_name": container['name'],
                "priority": item['priority'],
                "category": item['category'],
                "estimated_retrieval_time_minutes": round(retrieval_time, 2),
                "expiration_date": item['expiration_date']
            }
            
            matching_items.append(item_info)
    
    # Sort items by retrieval time (fastest first)
    matching_items.sort(key=lambda x: x['estimated_retrieval_time_minutes'])
    
    # Check for expiring items
    current_date = datetime.now().date()
    for item in matching_items:
        if item['expiration_date']:
            exp_date = datetime.strptime(item['expiration_date'], "%Y-%m-%d").date()
            days_to_expiry = (exp_date - current_date).days
            item['days_to_expiry'] = days_to_expiry
            
            # Flag items expiring soon
            if days_to_expiry <= 7:
                item['expiring_soon'] = True
    
    # Log the search action
    log_action("search_item", {
        "query": search_query,
        "category": category,
        "results_count": len(matching_items),
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    })
    
    return jsonify({
        "status": "success",
        "items": matching_items,
        "count": len(matching_items)
    }), 200

@app.route('/api/retrieve_item/<item_id>', methods=['POST'])
def retrieve_item(item_id):
    """Record retrieval of an item by an astronaut"""
    data = load_data()
    
    if item_id not in data['items']:
        return jsonify({"error": f"Item {item_id} not found"}), 404
    
    item = data['items'][item_id]
    container_id = item['location']
    
    # Update last accessed time
    data['items'][item_id]['last_accessed'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # Log retrieval
    log_action("retrieve_item", {
        "item_id": item_id,
        "item_name": item['name'],
        "container_id": container_id,
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    })
    
    save_data(data)
    
    return jsonify({
        "status": "success",
        "message": f"Item {item_id} retrieved",
        "item": data['items'][item_id]
    }), 200

# Feature 3: Rearrangement Optimization
def suggest_rearrangement(data: Dict, new_item: Dict) -> List[Dict]:
    """Suggest rearrangement of items to make space for new item"""
    item_volume = new_item['volume']
    item_weight = new_item['weight']
    
    # Check each container for potential rearrangements
    potential_moves = []
    
    # Try to find space by moving items between containers
    for container_id, container in data['containers'].items():
        if container['type'] != 'storage':
            continue
            
        # If this container could fit the new item with some rearrangement
        if container['total_volume'] - container['used_volume'] + item_volume <= container['total_volume'] and \
           container['max_weight'] - container['current_weight'] + item_weight <= container['max_weight']:
            
            # Look for items that could be moved elsewhere
            for item_id in container['items']:
                item = data['items'][item_id]
                
                # Check other containers that could hold this item
                for other_container_id, other_container in data['containers'].items():
                    if other_container_id == container_id or other_container['type'] != 'storage':
                        continue
                        
                    # Check if the other container has space
                    if other_container['used_volume'] + item['volume'] <= other_container['total_volume'] and \
                       other_container['current_weight'] + item['weight'] <= other_container['max_weight']:
                        
                        # This is a potential move
                        potential_moves.append({
                            "item_id": item_id,
                            "item_name": item['name'],
                            "from_container": container_id,
                            "to_container": other_container_id,
                            "volume_freed": item['volume'],
                            "weight_freed": item['weight']
                        })
    
    # Sort potential moves by volume freed (most efficient first)
    potential_moves.sort(key=lambda x: x['volume_freed'], reverse=True)
    
    # Create a rearrangement plan
    rearrangement_plan = []
    freed_volume = 0
    freed_weight = 0
    
    for move in potential_moves:
        if freed_volume >= item_volume and freed_weight >= item_weight:
            break
            
        rearrangement_plan.append(move)
        freed_volume += move['volume_freed']
        freed_weight += move['weight_freed']
    
    return rearrangement_plan if rearrangement_plan else []

@app.route('/api/rearrange_items', methods=['POST'])
def rearrange_items():
    """Execute a rearrangement plan"""
    data = load_data()
    plan = request.json.get('rearrangement_plan', [])
    
    if not plan:
        return jsonify({"error": "No rearrangement plan provided"}), 400
    
    # Execute each move in the plan
    for move in plan:
        item_id = move['item_id']
        from_container = move['from_container']
        to_container = move['to_container']
        
        if item_id not in data['items'] or \
           from_container not in data['containers'] or \
           to_container not in data['containers']:
            return jsonify({"error": f"Invalid move: {move}"}), 400
        
        item = data['items'][item_id]
        
        # Update containers
        data['containers'][from_container]['used_volume'] -= item['volume']
        data['containers'][from_container]['current_weight'] -= item['weight']
        data['containers'][from_container]['items'].remove(item_id)
        
        data['containers'][to_container]['used_volume'] += item['volume']
        data['containers'][to_container]['current_weight'] += item['weight']
        data['containers'][to_container]['items'].append(item_id)
        
        # Update item location
        data['items'][item_id]['location'] = to_container
        data['items'][item_id]['last_accessed'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    save_data(data)
    
    # Log the rearrangement
    log_action("rearrange_items", {
        "plan": plan,
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    })
    
    return jsonify({
        "status": "success",
        "message": "Rearrangement completed successfully",
        "moves_completed": len(plan)
    }), 200

# Feature 4: Waste Disposal Management
@app.route('/api/mark_as_waste', methods=['POST'])
def mark_as_waste():
    """Mark an item as waste and suggest disposal container"""
    data = load_data()
    request_data = request.json
    
    if not request_data or 'item_id' not in request_data:
        return jsonify({"error": "Item ID is required"}), 400
    
    item_id = request_data['item_id']
    reason = request_data.get('reason', 'used')  # 'used', 'expired', 'damaged', etc.
    
    if item_id not in data['items']:
        return jsonify({"error": f"Item {item_id} not found"}), 404
    
    item = data['items'][item_id]
    old_container_id = item['location']
    
    # Update item status
    data['items'][item_id]['status'] = 'waste'
    
    # Find appropriate waste container
    waste_container = find_waste_container(data, item)
    
    if not waste_container:
        return jsonify({
            "status": "error",
            "message": "No suitable waste container found. Create a new waste container."
        }), 400
    
    # Move item from current container to waste container
    # Update old container
    data['containers'][old_container_id]['used_volume'] -= item['volume']
    data['containers'][old_container_id]['current_weight'] -= item['weight']
    data['containers'][old_container_id]['items'].remove(item_id)
    
    # Update waste container
    data['waste_containers'][waste_container]['used_volume'] += item['volume']
    data['waste_containers'][waste_container]['current_weight'] += item['weight']
    
    # Update item location to indicate waste container
    data['items'][item_id]['location'] = f"waste_{waste_container}"
    
    save_data(data)
    
    # Log waste disposal
    log_action("mark_as_waste", {
        "item_id": item_id,
        "item_name": item['name'],
        "reason": reason,
        "waste_container": waste_container,
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    })
    
    return jsonify({
        "status": "success",
        "message": f"Item {item_id} marked as waste and assigned to waste container {waste_container}",
        "waste_container": waste_container
    }), 200

def find_waste_container(data: Dict, item: Dict) -> Optional[str]:
    """Find appropriate waste container for an item"""
    item_category = item['category']
    item_volume = item['volume']
    item_weight = item['weight']
    
    # Find suitable waste container
    suitable_containers = []
    
    for container_id, container in data['waste_containers'].items():
        # Check if container accepts this waste category
        if 'waste_categories' in container and item_category not in container['waste_categories'] and 'general' not in container['waste_categories']:
            continue
            
        # Check if container has enough space and weight capacity
        if container['used_volume'] + item_volume <= container['total_volume'] and \
           container['current_weight'] + item_weight <= container['max_weight']:
            
            # Calculate efficiency score (how well this item fits the container)
            remaining_space = container['total_volume'] - container['used_volume']
            space_efficiency = 1 - (remaining_space - item_volume) / container['total_volume']
            
            suitable_containers.append((space_efficiency, container_id))
    
    # Return the most efficient container
    suitable_containers.sort(reverse=True)
    return suitable_containers[0][1] if suitable_containers else None

# Feature 5: Cargo Return Planning
@app.route('/api/return_planning/<waste_container_id>', methods=['GET'])
def return_planning(waste_container_id):
    """Generate a return plan for a waste container"""
    data = load_data()
    
    if waste_container_id not in data['waste_containers']:
        return jsonify({"error": f"Waste container {waste_container_id} not found"}), 404
    
    container = data['waste_containers'][waste_container_id]
    
    # Get all waste items in this container
    waste_items = []
    total_volume = 0
    total_weight = 0
    
    for item_id, item in data['items'].items():
        if item['location'] == f"waste_{waste_container_id}":
            waste_items.append({
                "item_id": item_id,
                "name": item['name'],
                "category": item['category'],
                "volume": item['volume'],
                "weight": item['weight'],
                "status": item['status']
            })
            
            total_volume += item['volume']
            total_weight += item['weight']
    
    # Generate return plan
    return_plan = {
        "container_id": waste_container_id,
        "container_name": container['name'],
        "undock_date": container.get('undock_date', 'Not scheduled'),
        "waste_items": waste_items,
        "total_items": len(waste_items),
        "total_volume": total_volume,
        "total_weight": total_weight,
        "volume_utilization": (total_volume / container['total_volume']) * 100 if container['total_volume'] > 0 else 0,
        "weight_utilization": (total_weight / container['max_weight']) * 100 if container['max_weight'] > 0 else 0,
        "space_reclamation": {
            "volume_reclaimed": total_volume,
            "weight_reclaimed": total_weight
        }
    }
    
    # Log the planning activity
    log_action("return_planning", {
        "waste_container_id": waste_container_id,
        "total_items": len(waste_items),
        "total_volume": total_volume,
        "total_weight": total_weight,
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    })
    
    return jsonify({
        "status": "success",
        "return_plan": return_plan
    }), 200

@app.route('/api/confirm_return/<waste_container_id>', methods=['POST'])
def confirm_return(waste_container_id):
    """Confirm a waste container has been returned via undocking"""
    data = load_data()
    
    if waste_container_id not in data['waste_containers']:
        return jsonify({"error": f"Waste container {waste_container_id} not found"}), 404
    
    # Get all waste items in this container
    items_to_remove = []
    
    for item_id, item in data['items'].items():
        if item['location'] == f"waste_{waste_container_id}":
            items_to_remove.append(item_id)
    
    # Remove items and container
    for item_id in items_to_remove:
        del data['items'][item_id]
    
    # Store container info before deleting for the log
    container_info = data['waste_containers'][waste_container_id]
    
    # Remove the waste container
    del data['waste_containers'][waste_container_id]
    
    save_data(data)
    
    # Log the return confirmation
    log_action("confirm_return", {
        "waste_container_id": waste_container_id,
        "container_name": container_info['name'],
        "items_removed": len(items_to_remove),
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    })
    
    return jsonify({
        "status": "success",
        "message": f"Waste container {waste_container_id} confirmed returned",
        "items_removed": len(items_to_remove)
    }), 200

# Feature 6: Logging (already implemented throughout)
@app.route('/api/logs', methods=['GET'])
def get_logs():
    """Get system logs"""
    # Optional filters
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    action_type = request.args.get('action_type')
    limit = int(request.args.get('limit', 100))
    
    # Load logs
    logs = []
    if os.path.exists(LOG_FILE):
        with open(LOG_FILE, 'r') as f:
            logs = json.load(f)
    
    # Apply filters
    filtered_logs = logs
    
    if start_date:
        start = datetime.strptime(start_date, "%Y-%m-%d")
        filtered_logs = [log for log in filtered_logs 
                         if datetime.strptime(log['timestamp'], "%Y-%m-%d %H:%M:%S") >= start]
    
    if end_date:
        end = datetime.strptime(end_date, "%Y-%m-%d")
        filtered_logs = [log for log in filtered_logs 
                         if datetime.strptime(log['timestamp'], "%Y-%m-%d %H:%M:%S") <= end]
    
    if action_type:
        filtered_logs = [log for log in filtered_logs if log['action'] == action_type]
    
    # Limit results and sort by most recent first
    filtered_logs.sort(key=lambda x: x['timestamp'], reverse=True)
    limited_logs = filtered_logs[:limit]
    
    return jsonify({
        "status": "success",
        "total_logs": len(filtered_logs),
        "logs": limited_logs
    }), 200

# Additional API Endpoints for Container Management
@app.route('/api/add_container', methods=['POST'])
def add_container():
    """Add a new storage container"""
    data = load_data()
    container_data = request.json
    
    if not container_data or 'container_id' not in container_data:
        return jsonify({"error": "Invalid container data"}), 400
    
    container_id = container_data['container_id']
    
    if container_id in data['containers']:
        return jsonify({"error": f"Container ID {container_id} already exists"}), 400
    
    # Add new container
    data['containers'][container_id] = {
        "name": container_data['name'],
        "total_volume": float(container_data['total_volume']),
        "used_volume": 0.0,
        "max_weight": float(container_data['max_weight']),
        "current_weight": 0.0,
        "items": [],
        "type": container_data.get('type', 'storage'),
        "accessibility_factor": float(container_data.get('accessibility_factor', 0.5))
    }
    
    save_data(data)
    
    # Log the action
    log_action("add_container", {
        "container_id": container_id,
        "container_name": container_data['name'],
        "type": container_data.get('type', 'storage'),
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    })
    
    return jsonify({
        "status": "success",
        "message": f"Container {container_id} added successfully",
        "container": data['containers'][container_id]
    }), 201

@app.route('/api/add_waste_container', methods=['POST'])
def add_waste_container():
    """Add a new waste container"""
    data = load_data()
    container_data = request.json
    
    if not container_data or 'container_id' not in container_data:
        return jsonify({"error": "Invalid container data"}), 400
    
    container_id = container_data['container_id']
    
    if container_id in data['waste_containers']:
        return jsonify({"error": f"Waste container ID {container_id} already exists"}), 400
    
    # Add new waste container
    data['waste_containers'][container_id] = {
        "name": container_data['name'],
        "total_volume": float(container_data['total_volume']),
        "used_volume": 0.0,
        "max_weight": float(container_data['max_weight']),
        "current_weight": 0.0,
        "waste_categories": container_data.get('waste_categories', ['general']),
        "undock_date": container_data.get('undock_date')
    }
    
    save_data(data)
    
    # Log the action
    log_action("add_waste_container", {
        "container_id": container_id,
        "container_name": container_data['name'],
        "waste_categories": container_data.get('waste_categories', ['general']),
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    })
    
    return jsonify({
        "status": "success",
        "message": f"Waste container {container_id} added successfully",
        "container": data['waste_containers'][container_id]
    }), 201

@app.route('/api/get_storage_status', methods=['GET'])
def get_storage_status():
    """Get overall storage status and statistics"""
    data = load_data()
    
    # Calculate overall statistics
    total_storage_volume = 0
    used_storage_volume = 0
    total_storage_weight_capacity = 0
    current_storage_weight = 0
    
    total_waste_volume = 0
    used_waste_volume = 0
    total_waste_weight_capacity = 0
    current_waste_weight = 0
    
    # Items statistics
    total_active_items = 0
    total_waste_items = 0
    items_by_category = {}
    items_expiring_soon = 0
    
    # Get today's date for expiration calculation
    today = datetime.now().date()
    
    # Calculate container statistics
    storage_containers = []
    for container_id, container in data['containers'].items():
        total_storage_volume += container['total_volume']
        used_storage_volume += container['used_volume']
        total_storage_weight_capacity += container['max_weight']
        current_storage_weight += container['current_weight']
        
        # Calculate utilization percentages
        volume_utilization = (container['used_volume'] / container['total_volume']) * 100 if container['total_volume'] > 0 else 0
        weight_utilization = (container['current_weight'] / container['max_weight']) * 100 if container['max_weight'] > 0 else 0
        
        storage_containers.append({
            "container_id": container_id,
            "name": container['name'],
            "type": container['type'],
            "volume_utilization": round(volume_utilization, 2),
            "weight_utilization": round(weight_utilization, 2),
            "item_count": len(container['items']),
            "accessibility_factor": container['accessibility_factor']
        })
    
    # Calculate waste container statistics
    waste_containers = []
    for container_id, container in data['waste_containers'].items():
        total_waste_volume += container['total_volume']
        used_waste_volume += container['used_volume']
        total_waste_weight_capacity += container['max_weight']
        current_waste_weight += container['current_weight']
        
        # Calculate utilization percentages
        volume_utilization = (container['used_volume'] / container['total_volume']) * 100 if container['total_volume'] > 0 else 0
        weight_utilization = (container['current_weight'] / container['max_weight']) * 100 if container['max_weight'] > 0 else 0
        
        waste_containers.append({
            "container_id": container_id,
            "name": container['name'],
            "volume_utilization": round(volume_utilization, 2),
            "weight_utilization": round(weight_utilization, 2),
            "waste_categories": container.get('waste_categories', ['general']),
            "undock_date": container.get('undock_date')
        })
    
    # Calculate item statistics
    for item_id, item in data['items'].items():
        if item['status'] == 'active':
            total_active_items += 1
            
            # Count by category
            category = item.get('category', 'general')
            if category not in items_by_category:
                items_by_category[category] = 0
            items_by_category[category] += 1
            
            # Check for expiring items
            if item.get('expiration_date'):
                exp_date = datetime.strptime(item['expiration_date'], "%Y-%m-%d").date()
                days_to_expiry = (exp_date - today).days
                if days_to_expiry <= 7 and days_to_expiry >= 0:
                    items_expiring_soon += 1
        elif item['status'] == 'waste':
            total_waste_items += 1
    
    # Generate summary statistics
    storage_stats = {
        "total_volume": total_storage_volume,
        "used_volume": used_storage_volume,
        "volume_utilization": round((used_storage_volume / total_storage_volume) * 100, 2) if total_storage_volume > 0 else 0,
        "total_weight_capacity": total_storage_weight_capacity,
        "current_weight": current_storage_weight,
        "weight_utilization": round((current_storage_weight / total_storage_weight_capacity) * 100, 2) if total_storage_weight_capacity > 0 else 0,
        "container_count": len(data['containers'])
    }
    
    waste_stats = {
        "total_volume": total_waste_volume,
        "used_volume": used_waste_volume,
        "volume_utilization": round((used_waste_volume / total_waste_volume) * 100, 2) if total_waste_volume > 0 else 0,
        "total_weight_capacity": total_waste_weight_capacity,
        "current_weight": current_waste_weight,
        "weight_utilization": round((current_waste_weight / total_waste_weight_capacity) * 100, 2) if total_waste_weight_capacity > 0 else 0,
        "container_count": len(data['waste_containers'])
    }
    
    item_stats = {
        "total_active_items": total_active_items,
        "total_waste_items": total_waste_items,
        "items_by_category": items_by_category,
        "items_expiring_soon": items_expiring_soon
    }
    
    return jsonify({
        "status": "success",
        "storage_stats": storage_stats,
        "waste_stats": waste_stats,
        "item_stats": item_stats,
        "storage_containers": storage_containers,
        "waste_containers": waste_containers
    }), 200

@app.route('/api/expiring_items', methods=['GET'])
def get_expiring_items():
    """Get items that are expiring soon"""
    data = load_data()
    days = int(request.args.get('days', 7))  # Default to 7 days
    
    today = datetime.now().date()
    expiring_items = []
    
    for item_id, item in data['items'].items():
        if item['status'] != 'active' or not item.get('expiration_date'):
            continue
            
        exp_date = datetime.strptime(item['expiration_date'], "%Y-%m-%d").date()
        days_to_expiry = (exp_date - today).days
        
        if 0 <= days_to_expiry <= days:
            container = data['containers'][item['location']]
            
            expiring_items.append({
                "item_id": item_id,
                "name": item['name'],
                "days_to_expiry": days_to_expiry,
                "expiration_date": item['expiration_date'],
                "location": item['location'],
                "container_name": container['name'],
                "priority": item['priority'],
                "category": item['category']
            })
    
    # Sort by days to expiry (ascending)
    expiring_items.sort(key=lambda x: x['days_to_expiry'])
    
    return jsonify({
        "status": "success",
        "expiring_items": expiring_items,
        "count": len(expiring_items)
    }), 200

@app.route('/api/item/<item_id>', methods=['GET'])
def get_item(item_id):
    """Get detailed information about a specific item"""
    data = load_data()
    
    if item_id not in data['items']:
        return jsonify({"error": f"Item {item_id} not found"}), 404
    
    item = data['items'][item_id]
    
    # Get container information
    container_info = None
    if item['status'] == 'active':
        if item['location'] in data['containers']:
            container = data['containers'][item['location']]
            container_info = {
                "container_id": item['location'],
                "name": container['name'],
                "type": container['type'],
                "accessibility_factor": container['accessibility_factor']
            }
    elif item['status'] == 'waste':
        # Extract waste container ID from the location (format: "waste_container_id")
        waste_container_id = item['location'].replace("waste_", "")
        if waste_container_id in data['waste_containers']:
            container = data['waste_containers'][waste_container_id]
            container_info = {
                "container_id": waste_container_id,
                "name": container['name'],
                "type": "waste",
                "undock_date": container.get('undock_date')
            }
    
    # If the item has an expiration date, calculate days until expiry
    days_to_expiry = None
    if item.get('expiration_date'):
        exp_date = datetime.strptime(item['expiration_date'], "%Y-%m-%d").date()
        today = datetime.now().date()
        days_to_expiry = (exp_date - today).days
    
    # Compile item details
    item_details = {
        "item_id": item_id,
        "name": item['name'],
        "status": item['status'],
        "location": item['location'],
        "container": container_info,
        "priority": item['priority'],
        "category": item['category'],
        "volume": item['volume'],
        "weight": item['weight'],
        "arrival_date": item['arrival_date'],
        "last_accessed": item['last_accessed'],
        "expiration_date": item.get('expiration_date'),
        "days_to_expiry": days_to_expiry
    }
    
    # Log the view action
    log_action("view_item", {
        "item_id": item_id,
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    })
    
    return jsonify({
        "status": "success",
        "item": item_details
    }), 200

@app.route('/api/update_item/<item_id>', methods=['PUT'])
def update_item(item_id):
    """Update item information"""
    data = load_data()
    update_data = request.json
    
    if item_id not in data['items']:
        return jsonify({"error": f"Item {item_id} not found"}), 404
    
    item = data['items'][item_id]
    old_data = item.copy()  # For logging
    
    # Check if container is being changed
    new_container = update_data.get('location')
    old_container = item['location']
    
    if new_container and new_container != old_container and item['status'] == 'active':
        # Ensure new container exists
        if new_container not in data['containers']:
            return jsonify({"error": f"Container {new_container} not found"}), 404
        
        # Check if new container has enough space
        container = data['containers'][new_container]
        if container['used_volume'] + item['volume'] > container['total_volume']:
            return jsonify({"error": f"Not enough space in container {new_container}"}), 400
        
        if container['current_weight'] + item['weight'] > container['max_weight']:
            return jsonify({"error": f"Weight limit exceeded in container {new_container}"}), 400
        
        # Update old container
        data['containers'][old_container]['used_volume'] -= item['volume']
        data['containers'][old_container]['current_weight'] -= item['weight']
        data['containers'][old_container]['items'].remove(item_id)
        
        # Update new container
        data['containers'][new_container]['used_volume'] += item['volume']
        data['containers'][new_container]['current_weight'] += item['weight']
        data['containers'][new_container]['items'].append(item_id)
    
    # Update allowed fields
    for field in ['name', 'priority', 'expiration_date', 'category']:
        if field in update_data:
            data['items'][item_id][field] = update_data[field]
    
    # Always update last_accessed time
    data['items'][item_id]['last_accessed'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    save_data(data)
    
    # Log the update
    log_action("update_item", {
        "item_id": item_id,
        "old_data": old_data,
        "new_data": data['items'][item_id],
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    })
    
    return jsonify({
        "status": "success",
        "message": f"Item {item_id} updated successfully",
        "item": data['items'][item_id]
    }), 200

# Feature 7: Efficiency Monitoring
@app.route('/api/efficiency_metrics', methods=['GET'])
def get_efficiency_metrics():
    """Get system efficiency metrics"""
    data = load_data()
    
    # Load logs for time-based analysis
    logs = []
    if os.path.exists(LOG_FILE):
        with open(LOG_FILE, 'r') as f:
            logs = json.load(f)
    
    # Calculate space utilization efficiency
    total_storage_volume = sum(container['total_volume'] for container in data['containers'].values())
    used_storage_volume = sum(container['used_volume'] for container in data['containers'].values())
    
    space_utilization = (used_storage_volume / total_storage_volume * 100) if total_storage_volume > 0 else 0
    
    # Calculate retrieval efficiency (average time between searches and retrievals)
    retrieval_times = []
    search_timestamps = {}
    
    for log in logs:
        if log['action'] == 'search_item':
            for result in log['details'].get('results', []):
                search_timestamps[result] = datetime.strptime(log['timestamp'], "%Y-%m-%d %H:%M:%S")
        elif log['action'] == 'retrieve_item':
            item_id = log['details']['item_id']
            if item_id in search_timestamps:
                search_time = search_timestamps[item_id]
                retrieval_time = datetime.strptime(log['timestamp'], "%Y-%m-%d %H:%M:%S")
                time_diff = (retrieval_time - search_time).total_seconds()
                retrieval_times.append(time_diff)
    
    avg_retrieval_time = sum(retrieval_times) / len(retrieval_times) if retrieval_times else 0
    
    # Calculate waste management efficiency
    waste_utilization = 0
    if data['waste_containers']:
        total_waste_volume = sum(container['total_volume'] for container in data['waste_containers'].values())
        used_waste_volume = sum(container['used_volume'] for container in data['waste_containers'].values())
        waste_utilization = (used_waste_volume / total_waste_volume * 100) if total_waste_volume > 0 else 0
    
    # Calculate rearrangement efficiency
    rearrangement_logs = [log for log in logs if log['action'] == 'rearrange_items']
    avg_moves_per_rearrangement = sum(len(log['details']['plan']) for log in rearrangement_logs) / len(rearrangement_logs) if rearrangement_logs else 0
    
    # Calculate expiration management efficiency
    expired_items = 0
    for item_id, item in data['items'].items():
        if item.get('expiration_date'):
            exp_date = datetime.strptime(item['expiration_date'], "%Y-%m-%d").date()
            today = datetime.now().date()
            if exp_date < today and item['status'] == 'active':
                expired_items += 1
    
    total_items = len([i for i in data['items'].values() if i['status'] == 'active'])
    expiration_efficiency = 100 - (expired_items / total_items * 100) if total_items > 0 else 100
    
    # Compile efficiency metrics
    efficiency_metrics = {
        "space_utilization": round(space_utilization, 2),
        "average_retrieval_time_seconds": round(avg_retrieval_time, 2),
        "waste_management_efficiency": round(waste_utilization, 2),
        "rearrangement_efficiency": {
            "avg_moves_per_rearrangement": round(avg_moves_per_rearrangement, 2),
            "total_rearrangements": len(rearrangement_logs)
        },
        "expiration_management": {
            "efficiency_percentage": round(expiration_efficiency, 2),
            "expired_items": expired_items,
            "total_items": total_items
        }
    }
    
    return jsonify({
        "status": "success",
        "efficiency_metrics": efficiency_metrics
    }), 200

# Create an undock plan for a module
@app.route('/api/undock_plan', methods=['POST'])
def create_undock_plan():
    """Create an undock plan for returning cargo or waste"""
    data = load_data()
    plan_data = request.json
    
    if not plan_data or 'module_id' not in plan_data:
        return jsonify({"error": "Module ID is required"}), 400
    
    module_id = plan_data['module_id']
    undock_date = plan_data.get('undock_date', (datetime.now() + timedelta(days=7)).strftime("%Y-%m-%d"))
    plan_type = plan_data.get('type', 'waste')  # 'waste' or 'return'
    
    # If it's a waste container, mark the undock date
    if plan_type == 'waste' and module_id in data['waste_containers']:
        data['waste_containers'][module_id]['undock_date'] = undock_date
        
        # Get all waste items in this container
        waste_items = []
        for item_id, item in data['items'].items():
            if item['location'] == f"waste_{module_id}":
                waste_items.append(item_id)
        
        save_data(data)
        
        # Log the undock plan
        log_action("create_undock_plan", {
            "module_id": module_id,
            "undock_date": undock_date,
            "type": plan_type,
            "items_count": len(waste_items),
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        })
        
        return jsonify({
            "status": "success",
            "message": f"Undock plan created for waste container {module_id}",
            "undock_date": undock_date,
            "items_count": len(waste_items)
        }), 201
    else:
        return jsonify({"error": f"Module {module_id} not found or type mismatch"}), 404

# Initialize DB with some sample data if it doesn't exist
def initialize_sample_data():
    if not os.path.exists(DATA_FILE):
        sample_data = {
            "items": {
                "item_001": {
                    "name": "Food Packet A",
                    "location": "storage_001",
                    "priority": 4,
                    "expiration_date": (datetime.now() + timedelta(days=90)).strftime("%Y-%m-%d"),
                    "volume": 0.5,
                    "weight": 0.3,
                    "category": "food",
                    "status": "active",
                    "arrival_date": (datetime.now() - timedelta(days=10)).strftime("%Y-%m-%d"),
                    "last_accessed": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                },
                "item_002": {
                    "name": "Medical Kit",
                    "location": "storage_002",
                    "priority": 5,
                    "expiration_date": (datetime.now() + timedelta(days=180)).strftime("%Y-%m-%d"),
                    "volume": 2.0,
                    "weight": 1.5,
                    "category": "medical",
                    "status": "active",
                    "arrival_date": (datetime.now() - timedelta(days=5)).strftime("%Y-%m-%d"),
                    "last_accessed": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                }
            },
            "containers": {
                "storage_001": {
                    "name": "Main Storage A",
                    "total_volume": 100.0,
                    "used_volume": 0.5,
                    "max_weight": 200.0,
                    "current_weight": 0.3,
                    "items": ["item_001"],
                    "type": "storage",
                    "accessibility_factor": 0.9
                },
                "storage_002": {
                    "name": "Medical Storage",
                    "total_volume": 50.0,
                    "used_volume": 2.0,
                    "max_weight": 100.0,
                    "current_weight": 1.5,
                    "items": ["item_002"],
                    "type": "storage",
                    "accessibility_factor": 0.8
                }
            },
            "waste_containers": {
                "waste_001": {
                    "name": "General Waste",
                    "total_volume": 30.0,
                    "used_volume": 0.0,
                    "max_weight": 50.0,
                    "current_weight": 0.0,
                    "waste_categories": ["general", "organic"],
                    "undock_date": (datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d")
                }
            }
        }
        
        with open(DATA_FILE, 'w') as f:
            json.dump(sample_data, f, indent=2)

if __name__ == "__main__":
    # Initialize sample data if needed
    initialize_sample_data()
    app.run(debug=True, host='0.0.0.0', port=5000)
