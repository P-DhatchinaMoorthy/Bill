import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from flask import Flask, jsonify
from flask_cors import CORS
from src.config import Config
from src.extensions import db, migrate, mail
from user.user import User, Permission, UserPermission, AuditLog
from settings.company_settings import Settings

# register blueprints dynamically
from routes import register_routes

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)
    app.config['SECRET_KEY'] = 'your-secret-key-change-in-production'
    app.config['SESSION_TYPE'] = 'filesystem'

    # Enable CORS for all routes
    CORS(app, origins="*", methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"], allow_headers=["Content-Type", "Authorization"], supports_credentials=True)

    # Mail configuration
    app.config['MAIL_SERVER'] = 'smtp.gmail.com'
    app.config['MAIL_PORT'] = 587
    app.config['MAIL_USE_TLS'] = True
    app.config['MAIL_USERNAME'] = 'datchu15052003@gmail.com'
    app.config['MAIL_PASSWORD'] = 'uflq lwzt tvpo vdbs'
    app.config['MAIL_DEFAULT_SENDER'] = 'datchu15052003@gmail.com'
    
    # initialize extensions
    db.init_app(app)
    migrate.init_app(app, db)
    mail.init_app(app)
    
    # Import all models within app context to resolve relationships
    with app.app_context():
        from customers.customer import Customer
        from invoices.invoice import Invoice
        from invoices.invoice_item import InvoiceItem
        from payments.payment import Payment
        from products.product import Product
        from suppliers.supplier import Supplier
        from category.category import Category, SubCategory
        from stock_transactions.stock_transaction import StockTransaction

    # register routes/blueprints
    register_routes(app)

    @app.get("/")
    def index():
        return jsonify({"message": "Store Management API"}), 200
    
    @app.route('/api/test')
    def test():
        return jsonify({"message": "Backend Connected Successfully"}), 200
    
    @app.route('/logo.png')
    def serve_logo():
        from flask import send_file
        return send_file('logo.png', mimetype='image/png')
    
    @app.route('/addons/<filename>')
    def serve_addons(filename):
        from flask import send_file
        import os
        # Get absolute path to addons directory
        backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        addon_path = os.path.join(backend_dir, 'addons', filename)
        if os.path.exists(addon_path):
            return send_file(addon_path, mimetype='image/png')
        else:
            return jsonify({"error": "File not found"}), 404

    return app

if __name__ == "__main__":
    import logging
    import smtplib
    
    logging.getLogger('smtplib').setLevel(logging.ERROR)
    smtplib.SMTP.debuglevel = 0
    
    app = create_app()
    app.run(host="0.0.0.0", port=5000, debug=app.config["DEBUG"])
