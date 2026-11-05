# National Local Delivery & Concierge Network

A multi-city, peer-to-peer local delivery and merchant concierge operating system designed to support independent local business nodes while offering fair driver compensation and secure checkout.

## 🌟 Core Features

- **Multi-City Node Framework:** Supports regional partner nodes and corporate targets across cities (e.g., Grass Valley, CA and Fort Wayne, IN) with dynamic fee scaling.
- **Subsidized Local Rates vs. Corporate Surcharges:** Built-in economic incentives favoring local partner nodes with lower delivery fees, while applying heavier delivery taxes to major corporate chains.
- **Live Store & Item Search:** Real-time item lookup across partner menus so customers can search for specific items, view exact pricing, and add them instantly to their cart.
- **Custom Town Concierge:** "Order Anything in Town" workflow supporting custom store pickups with built-in safety exclusions (no alcohol/tobacco) and optional upfront cash-advance risk fee handling.
- **Driver Tipping & Fair Payouts:** Direct driver tip integration ($0 to $10+) at checkout, combining base delivery fees and tips into a transparent total driver payout displayed on both checkout and dispatch.
- **Secure Stripe Elements Checkout:** End-to-end payment intent handling securely injected via Flask environment configuration.
- **Real-Time Dispatch Dashboard (`/dispatch`):** Live polling command center displaying active pickup orders, total amounts, item descriptions, and driver payouts with one-click order clearing (`orders.json`).

---

## 🛠️ Project Structure

```text
├── server.py              # Flask backend, Stripe intent routing, and API endpoints
├── merchants.json         # Merchant directory, node types, and structured item menus
├── orders.json            # Persistent local ledger for active dispatches
├── .env                   # Secure environment variables (Stripe API keys)
└── templates/
    ├── index.html         # Customer storefront, search engine, tip selector, and Stripe Elements
    └── dispatch.html      # Real-time driver dispatch command center and queue management