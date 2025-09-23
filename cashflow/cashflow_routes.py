from flask import Blueprint, request, jsonify
from cashflow.cashflow_service import CashFlowService
from user.enhanced_auth_middleware import require_permission_jwt
from user.audit_logger import audit_decorator
from decimal import Decimal
from src.extensions import db
from returns.product_return import ProductReturn
from customers.customer import Customer
from products.product import Product

bp = Blueprint("cashflow", __name__)

@bp.route("/customer-payments", methods=["GET"])
@require_permission_jwt('cashflow', 'read')
def get_customer_payments():
    """Get all payments received from customers"""
    try:
        result = CashFlowService.get_customer_payments()
        return jsonify(result), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@bp.route("/customer-refunds", methods=["GET"])
@require_permission_jwt('cashflow', 'read')
def get_customer_refunds():
    """Get customer adjustment refunds (exchanges where we pay customer extra)"""
    try:
        # Get only adjustment refunds where we pay customer extra
        refunds = db.session.query(
            ProductReturn, Customer, Product
        ).join(Customer, ProductReturn.customer_id == Customer.id
        ).join(Product, ProductReturn.product_id == Product.id).filter(
            ProductReturn.return_type == 'exchange',
            ProductReturn.refund_amount > 0
        ).order_by(ProductReturn.return_date.desc()).all()
        
        customer_refunds = []
        total_paid = Decimal('0')
        
        for adjustment, customer, product in refunds:
            amount = Decimal(adjustment.refund_amount or 0)
            total_paid += amount
            
            customer_refunds.append({
                "adjustment_id": adjustment.id,
                "return_number": adjustment.return_number,
                "customer_id": customer.id,
                "customer_name": customer.contact_person,
                "business_name": customer.business_name,
                "old_product": product.product_name,
                "new_product": adjustment.exchange_product.product_name if adjustment.exchange_product else None,
                "amount_paid": CashFlowService.format_decimal(amount),
                "adjustment_date": adjustment.return_date.isoformat(),
                "status": adjustment.status,
                "reason": "Adjustment - We pay customer extra amount for product exchange"
            })
        
        result = {
            "customer_adjustment_refunds": customer_refunds,
            "total_paid": CashFlowService.format_decimal(total_paid),
            "count": len(customer_refunds)
        }
        return jsonify(result), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@bp.route("/supplier-payments", methods=["GET"])
@require_permission_jwt('cashflow', 'read')
def get_supplier_payments():
    """Get all payments made to suppliers"""
    try:
        result = CashFlowService.get_supplier_payments()
        return jsonify(result), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@bp.route("/supplier-receipts", methods=["GET"])
@require_permission_jwt('cashflow', 'read')
def get_supplier_receipts():
    """Get all payments received from suppliers"""
    try:
        result = CashFlowService.get_supplier_receipts()
        return jsonify(result), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@bp.route("/summary", methods=["GET"])
@require_permission_jwt('cashflow', 'read')
def get_cashflow_summary():
    """Get overall cash flow summary with detailed breakdown"""
    try:
        result = CashFlowService.get_cashflow_summary()
        return jsonify(result), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@bp.route("/detailed", methods=["GET"])
@require_permission_jwt('cashflow', 'read')
def get_detailed_cashflow():
    """Get detailed cash flow with all transaction types"""
    try:
        customer_payments = CashFlowService.get_customer_payments()
        customer_refunds = CashFlowService.get_customer_refunds()
        supplier_payments = CashFlowService.get_supplier_payments()
        supplier_receipts = CashFlowService.get_supplier_receipts()
        
        result = {
            "customer_payments": customer_payments,
            "customer_refunds": customer_refunds,
            "supplier_payments": supplier_payments,
            "supplier_refunds": supplier_receipts
        }
        return jsonify(result), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500