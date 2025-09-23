from decimal import Decimal
from datetime import datetime
from src.extensions import db
from payments.payment import Payment
from returns.product_return import ProductReturn, DamagedProduct
from stock_transactions.stock_transaction import StockTransaction
from customers.customer import Customer
from suppliers.supplier import Supplier
from products.product import Product

class CashFlowService:
    
    @staticmethod
    def get_customer_payments():
        """Get all payments received from customers (includes adjustment payments where customer pays us extra)"""
        try:
            # Get all successful payments from customers
            payments = db.session.query(
                Payment, Customer
            ).join(Customer, Payment.customer_id == Customer.id).filter(
                Payment.payment_status.in_(['Successful', 'Partially Paid']),
                Payment.amount_paid > 0
            ).order_by(Payment.payment_date.desc()).all()
            
            # Get adjustment payments where customer pays us extra
            adjustments = db.session.query(
                ProductReturn, Customer, Product
            ).join(Customer, ProductReturn.customer_id == Customer.id
            ).join(Product, ProductReturn.product_id == Product.id).filter(
                ProductReturn.return_type == 'exchange',
                ProductReturn.exchange_price_difference > 0,
                ProductReturn.refund_amount == 0
            ).order_by(ProductReturn.return_date.desc()).all()
            
            customer_payments = []
            total_received = Decimal('0')
            
            # Add regular payments
            for payment, customer in payments:
                amount = Decimal(payment.amount_paid or 0)
                total_received += amount
                
                customer_payments.append({
                    "payment_id": payment.id,
                    "invoice_id": payment.invoice_id,
                    "customer_id": customer.id,
                    "customer_name": customer.contact_person,
                    "business_name": customer.business_name,
                    "amount_paid": CashFlowService.format_decimal(amount),
                    "payment_method": payment.payment_method,
                    "payment_date": payment.payment_date.isoformat(),
                    "transaction_reference": payment.transaction_reference,
                    "payment_type": "regular_payment",
                    "status": payment.payment_status
                })
            
            # Add adjustment payments
            for adjustment, customer, product in adjustments:
                amount = Decimal(adjustment.exchange_price_difference or 0)
                total_received += amount
                
                customer_payments.append({
                    "payment_id": f"ADJ-{adjustment.id}",
                    "invoice_id": adjustment.original_invoice_id,
                    "customer_id": customer.id,
                    "customer_name": customer.contact_person,
                    "business_name": customer.business_name,
                    "amount_paid": CashFlowService.format_decimal(amount),
                    "payment_method": "adjustment",
                    "payment_date": adjustment.return_date.isoformat(),
                    "transaction_reference": adjustment.return_number,
                    "payment_type": "adjustment_payment",
                    "status": "Completed",
                    "adjustment_details": f"Customer pays extra for exchange: {product.product_name} -> {adjustment.exchange_product.product_name if adjustment.exchange_product else 'N/A'}"
                })
            
            return {
                "customer_payments": customer_payments,
                "total_received": CashFlowService.format_decimal(total_received),
                "count": len(customer_payments)
            }
        except Exception as e:
            raise Exception(f"Error fetching customer payments: {str(e)}")
    
    @staticmethod
    def get_customer_refunds():
        """Get all refunds paid to customers (returns, damaged products, and adjustments)"""
        try:
            # Get all returns with refund amounts (including all statuses except cancelled)
            refunds = db.session.query(
                ProductReturn, Customer, Product
            ).join(Customer, ProductReturn.customer_id == Customer.id
            ).join(Product, ProductReturn.product_id == Product.id).filter(
                ProductReturn.refund_amount > 0,
                ProductReturn.status.in_(['Pending', 'Processed', 'Completed'])
            ).order_by(ProductReturn.return_date.desc()).all()
            
            customer_refunds = []
            total_refunded = Decimal('0')
            
            for refund, customer, product in refunds:
                amount = Decimal(refund.refund_amount or 0)
                total_refunded += amount
                
                # Determine refund type and reason
                refund_type = refund.return_type
                reason = refund.reason
                
                if refund.return_type == 'exchange':
                    refund_type = 'adjustment_refund'
                    reason = f"Adjustment - We pay customer extra amount for product exchange"
                
                customer_refunds.append({
                    "return_id": refund.id,
                    "return_number": refund.return_number,
                    "customer_id": customer.id,
                    "customer_name": customer.contact_person,
                    "business_name": customer.business_name,
                    "product_name": product.product_name,
                    "refund_amount": CashFlowService.format_decimal(amount),
                    "refund_type": refund_type,
                    "reason": reason,
                    "return_date": refund.return_date.isoformat(),
                    "quantity_returned": refund.quantity_returned,
                    "exchange_product": refund.exchange_product.product_name if refund.exchange_product else None
                })
            
            return {
                "customer_refunds": customer_refunds,
                "total_refunded": CashFlowService.format_decimal(total_refunded),
                "count": len(customer_refunds)
            }
        except Exception as e:
            raise Exception(f"Error fetching customer refunds: {str(e)}")
    
    @staticmethod
    def get_supplier_payments():
        """Get all payments made to suppliers"""
        try:
            import json
            # Get all purchase transactions
            transactions = db.session.query(
                StockTransaction, Supplier
            ).join(Supplier, StockTransaction.supplier_id == Supplier.id).filter(
                StockTransaction.transaction_type == 'Purchase'
            ).order_by(StockTransaction.transaction_date.desc()).all()
            
            supplier_payments = []
            total_paid = Decimal('0')
            
            for transaction, supplier in transactions:
                # Extract payment info from notes
                payment_amount = Decimal('0')
                payment_method = None
                payment_status = None
                transaction_reference = None
                products_info = []
                
                if transaction.notes:
                    try:
                        payment_info = json.loads(transaction.notes)
                        payment_amount = Decimal(payment_info.get('payment_amount', '0'))
                        payment_method = payment_info.get('payment_method')
                        payment_status = payment_info.get('payment_status')
                        transaction_reference = payment_info.get('transaction_reference')
                        products_info = payment_info.get('products', [])
                    except (json.JSONDecodeError, ValueError):
                        pass
                
                # Only include transactions with actual payments
                if payment_amount > 0:
                    total_paid += payment_amount
                    
                    # Get product names from stored info or fallback to single product
                    product_names = []
                    if products_info:
                        product_names = [p.get('name', '') for p in products_info]
                    else:
                        product = Product.query.get(transaction.product_id)
                        if product:
                            product_names = [product.product_name]
                    
                    supplier_payments.append({
                        "transaction_id": transaction.id,
                        "supplier_id": supplier.id,
                        "supplier_name": supplier.contact_person,
                        "business_name": supplier.name,
                        "products": product_names,
                        "quantity": transaction.quantity,
                        "amount_paid": str(payment_amount),
                        "payment_method": payment_method,
                        "payment_status": payment_status,
                        "transaction_date": transaction.transaction_date.isoformat(),
                        "reference_number": transaction.reference_number,
                        "transaction_reference": transaction_reference
                    })
            
            return {
                "supplier_payments": supplier_payments,
                "total_paid": str(total_paid),
                "count": len(supplier_payments)
            }
        except Exception as e:
            raise Exception(f"Error fetching supplier payments: {str(e)}")
    
    @staticmethod
    def get_supplier_receipts():
        """Get all payments received from suppliers (supplier returns/refunds)"""
        try:
            # Get supplier damage returns where we received money
            from damage.supplier_return import SupplierReturn
            from returns.product_return import DamagedProduct
            
            receipts = db.session.query(
                SupplierReturn, Supplier
            ).join(Supplier, SupplierReturn.supplier_id == Supplier.id).filter(
                SupplierReturn.refund_amount > 0,
                SupplierReturn.status == 'Completed'
            ).order_by(SupplierReturn.return_date.desc()).all()
            
            supplier_receipts = []
            total_received = Decimal('0')
            
            for receipt, supplier in receipts:
                amount = Decimal(receipt.refund_amount or 0)
                total_received += amount
                
                # Get product info from damaged product
                damaged_product = DamagedProduct.query.get(receipt.damaged_product_id)
                product = Product.query.get(damaged_product.product_id) if damaged_product else None
                
                supplier_receipts.append({
                    "return_id": receipt.id,
                    "return_number": receipt.return_number,
                    "supplier_id": supplier.id,
                    "supplier_name": supplier.contact_person,
                    "business_name": supplier.name,
                    "product_name": product.product_name if product else 'Unknown Product',
                    "refund_amount": str(amount),
                    "return_type": receipt.return_type,
                    "return_date": receipt.return_date.isoformat(),
                    "quantity_returned": receipt.quantity_returned,
                    "status": receipt.status
                })
            
            return {
                "supplier_receipts": supplier_receipts,
                "total_received": str(total_received),
                "count": len(supplier_receipts)
            }
        except Exception as e:
            # If supplier returns don't exist, return empty
            return {
                "supplier_receipts": [],
                "total_received": "0.00",
                "count": 0
            }
    
    @staticmethod
    def format_decimal(value):
        """Format decimal to 2 decimal places"""
        return f"{Decimal(str(value)):.2f}"
    
    @staticmethod
    def get_cashflow_summary():
        """Get overall cash flow summary with detailed breakdown"""
        try:
            # Get all cash inflows
            customer_payments = CashFlowService.get_customer_payments()
            supplier_receipts = CashFlowService.get_supplier_receipts()
            
            total_inflow = Decimal(customer_payments['total_received']) + Decimal(supplier_receipts['total_received'])
            
            # Get all cash outflows
            customer_refunds = CashFlowService.get_customer_refunds()
            supplier_payments = CashFlowService.get_supplier_payments()
            
            total_outflow = Decimal(customer_refunds['total_refunded']) + Decimal(supplier_payments['total_paid'])
            
            # Calculate net cash flow
            net_cashflow = total_inflow - total_outflow
            
            return {
                "cash_inflow": {
                    "customer_payments": CashFlowService.format_decimal(customer_payments['total_received']),
                    "supplier_refunds": CashFlowService.format_decimal(supplier_receipts['total_received']),
                    "total_inflow": CashFlowService.format_decimal(total_inflow)
                },
                "cash_outflow": {
                    "customer_refunds": CashFlowService.format_decimal(customer_refunds['total_refunded']),
                    "supplier_payments": CashFlowService.format_decimal(supplier_payments['total_paid']),
                    "total_outflow": CashFlowService.format_decimal(total_outflow)
                },
                "net_cashflow": CashFlowService.format_decimal(net_cashflow),
                "detailed_breakdown": {
                    "customer_transactions": {
                        "payments_received": {
                            "amount": CashFlowService.format_decimal(customer_payments['total_received']),
                            "count": customer_payments['count'],
                            "transactions": customer_payments['customer_payments']
                        },
                        "refunds_given": {
                            "amount": CashFlowService.format_decimal(customer_refunds['total_refunded']),
                            "count": customer_refunds['count'],
                            "transactions": customer_refunds['customer_refunds']
                        }
                    },
                    "supplier_transactions": {
                        "payments_made": {
                            "amount": CashFlowService.format_decimal(supplier_payments['total_paid']),
                            "count": supplier_payments['count'],
                            "transactions": supplier_payments['supplier_payments']
                        },
                        "refunds_received": {
                            "amount": CashFlowService.format_decimal(supplier_receipts['total_received']),
                            "count": supplier_receipts['count'],
                            "transactions": supplier_receipts['supplier_receipts']
                        }
                    }
                },
                "summary": {
                    "total_customer_transactions": customer_payments['count'] + customer_refunds['count'],
                    "total_supplier_transactions": supplier_payments['count'] + supplier_receipts['count'],
                    "cash_position": "Positive" if net_cashflow > 0 else "Negative" if net_cashflow < 0 else "Neutral"
                }
            }
        except Exception as e:
            raise Exception(f"Error generating cash flow summary: {str(e)}")