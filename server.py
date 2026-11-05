from flask import Flask, render_template, request, jsonify
import stripe
import json
import os
from dotenv import dotenv_values

config = dotenv_values(".env")
stripe.api_key = config.get("STRIPE_SECRET_KEY")

app = Flask(__name__)

MERCHANTS_FILE = "merchants.json"
ORDERS_FILE = "orders.json"


def load_merchants():
    if os.path.exists(MERCHANTS_FILE):
        with open(MERCHANTS_FILE, "r") as f:
            return json.load(f)
    return {}


def load_orders():
    if os.path.exists(ORDERS_FILE):
        with open(ORDERS_FILE, "r") as f:
            return json.load(f)
    return []


def save_order(order_data):
    orders = load_orders()
    if any(o.get('payment_intent_id') == order_data.get('payment_intent_id') for o in orders):
        return
    orders.append(order_data)
    with open(ORDERS_FILE, "w") as f:
        json.dump(orders, f, indent=4)


@app.route('/')
def index():
    pub_key = config.get("STRIPE_PUBLISHABLE_KEY", "pk_test_TYooMQauvdEDq54NiTphI7jx")
    return render_template('index.html', stripe_publishable_key=pub_key)


@app.route('/dispatch')
def dispatch_dashboard():
    return render_template('dispatch.html')


@app.route('/api/merchants', methods=['GET'])
def get_merchants():
    city_filter = request.args.get('city')
    merchants = load_merchants()
    merchant_list = []
    for key, data in merchants.items():
        data['id'] = key
        if not city_filter or data.get('city', '').lower() == city_filter.lower():
            merchant_list.append(data)
    return jsonify(merchant_list)


@app.route('/api/search-items', methods=['GET'])
def search_items():
    query = request.args.get('q', '').lower()
    city_filter = request.args.get('city', '').lower()
    merchants = load_merchants()
    results = []

    for m_id, m_data in merchants.items():
        if city_filter and m_data.get('city', '').lower() != city_filter:
            continue
        for item in m_data.get('menu', []):
            if not query or query in item['name'].lower() or query in item['description'].lower() or query in m_data[
                'name'].lower():
                results.append({
                    "merchant_id": m_id,
                    "merchant_name": m_data['name'],
                    "city": m_data['city'],
                    "item_id": item['id'],
                    "item_name": item['name'],
                    "price": item['price'],
                    "description": item['description']
                })
    return jsonify(results)


@app.route('/api/calculate-fee', methods=['POST'])
def calculate_fee():
    data = request.json
    merchant_id = data.get('merchant_id')
    is_custom_concierge = data.get('is_custom_concierge', False)

    if is_custom_concierge:
        base_fee = 5.00
        requires_upfront_funding = data.get('upfront_funding', False)
        if requires_upfront_funding:
            base_fee += 4.00
        return jsonify({
            "merchant_name": "Custom Town Concierge",
            "is_node_partner": False,
            "delivery_fee": base_fee,
            "message": "Custom town delivery fee calculated."
        })

    merchants = load_merchants()
    merchant = merchants.get(merchant_id)
    if not merchant:
        return jsonify({"error": "Merchant not found"}), 404

    delivery_fee = merchant["base_delivery_fee"]
    is_node = merchant["type"] == "node_partner"

    return jsonify({
        "merchant_name": merchant["name"],
        "is_node_partner": is_node,
        "delivery_fee": delivery_fee,
        "message": "Local node discount applied!" if is_node else "Corporate delivery tax applied."
    })


@app.route('/create-payment-intent', methods=['POST'])
def create_payment_intent():
    try:
        data = request.json
        merchant_id = data.get('merchant_id')
        item_total = int(data.get('item_total_cents'))
        is_concierge = data.get('is_custom_concierge', False)
        upfront_funding = data.get('upfront_funding', False)
        tip_amount_dollars = float(data.get('tip_amount', 0.0))

        if is_concierge:
            merchant_name = "Custom Town Concierge"
            delivery_fee_dollars = 9.00 if upfront_funding else 5.00
        else:
            merchants = load_merchants()
            merchant = merchants.get(merchant_id)
            if not merchant:
                return jsonify({"error": "Invalid merchant"}), 400
            merchant_name = merchant["name"]
            delivery_fee_dollars = merchant["base_delivery_fee"]

        delivery_fee_cents = int(delivery_fee_dollars * 100)
        tip_cents = int(tip_amount_dollars * 100)
        total_amount = item_total + delivery_fee_cents + tip_cents

        total_driver_payout = delivery_fee_dollars + tip_amount_dollars

        intent = stripe.PaymentIntent.create(
            amount=total_amount,
            currency='usd',
            automatic_payment_methods={'enabled': True},
            metadata={
                "merchant_name": merchant_name,
                "delivery_fee": delivery_fee_dollars,
                "tip_amount": tip_amount_dollars,
                "total_driver_payout": total_driver_payout
            }
        )

        save_order({
            "payment_intent_id": intent.id,
            "merchant_name": merchant_name,
            "total_amount": total_amount / 100.0,
            "delivery_fee": delivery_fee_dollars,
            "tip_amount": tip_amount_dollars,
            "driver_payout": total_driver_payout,
            "status": "Pending Dispatch"
        })

        return jsonify({
            'clientSecret': intent.client_secret,
            'driverPayout': total_driver_payout,
            'totalAmount': total_amount / 100.0
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 403


@app.route('/api/orders', methods=['GET'])
def get_orders():
    return jsonify(load_orders())


@app.route('/api/orders/<payment_intent_id>', methods=['DELETE'])
def delete_order(payment_intent_id):
    orders = load_orders()
    updated_orders = [o for o in orders if o.get('payment_intent_id') != payment_intent_id]

    with open(ORDERS_FILE, "w") as f:
        json.dump(updated_orders, f, indent=4)

    return jsonify({"success": True, "message": "Order deleted"})


if __name__ == '__main__':
    app.run(port=4242, debug=True)