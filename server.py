import os
import math
from flask import Flask, render_template, request, jsonify
from google.cloud import firestore
from spiral_agent import DriverNodeSpiralHarvester

app = Flask(__name__, template_folder='templates')
db = firestore.Client(project='local-delivery-matrix')


@app.route('/', methods=['GET'])
def storefront():
    """Customer and driver storefront portal interface."""
    return render_template('index.html')


@app.route('/api/check-and-map-region', methods=['POST'])
def check_and_map_region():
    """Automatically anchor and execute the spiral harvester for the driver's private matrix."""
    data = request.get_json() or {}
    lat = data.get('lat')
    lon = data.get('lon')
    radius = data.get('radius_miles', 10.0)
    driver_id = data.get('driver_id', 'default_driver')

    if not lat or not lon:
        return jsonify({"error": "Missing coordinates"}), 400

    try:
        harvester = DriverNodeSpiralHarvester(anchor_lat=float(lat), anchor_lng=float(lon),
                                              outer_radius_miles=float(radius))
        nodes_mapped = harvester.execute_and_sync(driver_id)

        return jsonify({
            "status": "success",
            "message": f"Sector mapped for {driver_id}. {nodes_mapped} nodes synchronized.",
            "anchor": {"lat": lat, "lon": lon}
        }), 200
    except Exception as e:
        print(f"Error mapping region: {e}")
        return jsonify({"error": str(e)}), 500


@app.route('/api/driver/nodes', methods=['POST'])
def get_driver_nodes():
    """Fetch only active, QR-activated store nodes and customer delivery orders for the driver."""
    data = request.get_json() or {}
    driver_id = data.get('driver_id')

    if not driver_id:
        return jsonify([]), 400

    try:
        nodes_ref = db.collection('drivers').document(driver_id).collection('radar_matrix').stream()
        nodes = []
        for node in nodes_ref:
            node_data = node.to_dict()
            # Only display nodes that are QR-activated by the merchant or have active customer orders
            if node_data.get('is_active', False) or node_data.get('has_active_order', False):
                nodes.append(node_data)

        return jsonify(nodes), 200
    except Exception as e:
        print(f"Error fetching driver nodes: {e}")
        return jsonify([]), 500


@app.route('/api/driver/prospects', methods=['POST'])
def get_driver_prospects():
    """Fetch unactivated local stores in the sector to serve as QR drop-card targets for drivers out to 10 miles."""
    data = request.get_json() or {}
    driver_id = data.get('driver_id')
    curr_lat = data.get('lat')
    curr_lng = data.get('lon')

    if not driver_id:
        return jsonify([]), 400

    try:
        nodes_ref = db.collection('drivers').document(driver_id).collection('radar_matrix').stream()
        prospects = []

        for node in nodes_ref:
            node_data = node.to_dict()
            if not node_data.get('is_active', False):
                store_lat = node_data.get('lat')
                store_lng = node_data.get('lng')

                if curr_lat and curr_lng and store_lat and store_lng:
                    lat_diff = store_lat - float(curr_lat)
                    lng_diff = store_lng - float(curr_lng)
                    distance = math.sqrt(lat_diff ** 2 + lng_diff ** 2) * 69.0
                    node_data['distance_miles'] = round(distance, 1)
                else:
                    node_data['distance_miles'] = 0.0

                prospects.append(node_data)

        # Sort prospects by proximity (closest first) and return all across the full 10-mile radius
        prospects.sort(key=lambda x: x.get('distance_miles', 0.0))
        return jsonify(prospects), 200
    except Exception as e:
        print(f"Error fetching prospects: {e}")
        return jsonify([]), 500


@app.route('/api/merchant/activate', methods=['POST'])
def activate_merchant():
    """Endpoint triggered when a merchant scans their QR code and activates their node."""
    data = request.get_json() or {}
    node_id = data.get('node_id')
    driver_id = data.get('driver_id')

    if not node_id or not driver_id:
        return jsonify({"error": "Missing node_id or driver_id"}), 400

    try:
        db.collection('drivers').document(driver_id).collection('radar_matrix').document(node_id).update(
            {"is_active": True})
        db.collection('stores').document(node_id).update({"is_active": True})
        return jsonify({"status": "success", "message": f"Merchant {node_id} successfully activated!"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port, debug=False)