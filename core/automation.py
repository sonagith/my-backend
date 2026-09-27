# Backend/core/automation.py
import requests
import re
from datetime import datetime
from db.database import SessionLocal
from db import models

# ==========================================
# 🔴 API KEYS YAHAN DALEIN (Ya .env se lein)
# ==========================================
MSG91_AUTH_KEY = "YOUR_MSG91_AUTH_KEY_HERE"
MSG91_SENDER_ID = "GHRPLT"

WA_TOKEN = "YOUR_META_WHATSAPP_TOKEN_HERE"
WA_PHONE_NUMBER_ID = "YOUR_WA_PHONE_NUMBER_ID_HERE"

def clean_phone_number(phone: str):
    """ +91 98765 43210 ko 919876543210 mein convert karta hai API ke liye """
    if not phone:
        return ""
    # Sirf digits rakho
    clean_num = re.sub(r'\D', '', phone)
    # Agar 10 digit ka hai, toh aage 91 laga do
    if len(clean_num) == 10:
        clean_num = "91" + clean_num
    return clean_num

def send_real_sms(phone: str, message: str):
    """ MSG91 API ke through actual SMS bhejna """
    clean_num = clean_phone_number(phone)
    if not clean_num or not MSG91_AUTH_KEY or MSG91_AUTH_KEY == "YOUR_MSG91_AUTH_KEY_HERE":
        print("⚠️ SMS skipped: Invalid phone or MSG91 Key missing.")
        return False
        
    url = "https://api.msg91.com/api/v5/sendsms"
    payload = {
        "sender": MSG91_SENDER_ID,
        "route": "4",
        "country": "91",
        "sms": [{"message": message, "to": [clean_num]}]
    }
    headers = {"authkey": MSG91_AUTH_KEY, "Content-Type": "application/json"}
    
    try:
        response = requests.post(url, json=payload, headers=headers)
        if response.status_code == 200:
            return True
    except Exception as e:
        print(f"SMS API Error: {e}")
    return False

def send_real_whatsapp(phone: str, message: str):
    """ Meta WhatsApp Cloud API ke through actual message bhejna """
    clean_num = clean_phone_number(phone)
    if not clean_num or not WA_TOKEN or WA_TOKEN == "YOUR_META_WHATSAPP_TOKEN_HERE":
        print("⚠️ WhatsApp skipped: Invalid phone or WA Token missing.")
        return False
        
    url = f"https://graph.facebook.com/v17.0/{WA_PHONE_NUMBER_ID}/messages"
    payload = {
        "messaging_product": "whatsapp",
        "to": clean_num,
        "type": "text",
        "text": {"body": message}
    }
    headers = {
        "Authorization": f"Bearer {WA_TOKEN}",
        "Content-Type": "application/json"
    }
    
    try:
        response = requests.post(url, json=payload, headers=headers)
        if response.status_code in [200, 201]:
            return True
        else:
            print(f"WA API Failed: {response.text}")
    except Exception as e:
        print(f"WhatsApp API Error: {e}")
    return False

def format_message(template_body: str, plot: models.Plot, profile: models.BusinessProfile):
    """Database ki values ko {{placeholders}} ki jagah replace karta hai"""
    if not template_body:
        return ""
        
    client_name = plot.client.name if plot.client else "Client"
    staff = plot.assigned_staff
    
    replacements = {
        "{{clientName}}": client_name.split()[0],
        "{{plotNumber}}": plot.plot_no or "—",
        "{{invoiceNumber}}": f"{plot.plot_no}-INV",
        "{{installmentAmount}}": f"₹{plot.installment_amount:,.0f}" if plot.installment_amount else "₹0",
        "{{dueDate}}": plot.due_date.strftime("%d %b %Y") if plot.due_date else "—",
        "{{outstandingBalance}}": f"₹{plot.total_due_balance:,.0f}",
        "{{vendorName}}": profile.business_name if profile else "Our Company",
        "{{paymentLink}}": f"https://pay.gharpilot.in/pay/{plot.id}",
        "{{staffName}}": staff.name if staff else "Support Team",
        "{{staffPhone}}": staff.phone if staff else "—"
    }
    
    msg = template_body
    for key, val in replacements.items():
        msg = msg.replace(key, str(val))
    return msg

def run_daily_reminders():
    db = SessionLocal()
    print(f"⚙️ Running Daily Automation Job at {datetime.now()}")
    
    try:
        auto = db.query(models.AutomationSettings).first()
        profile = db.query(models.BusinessProfile).first()
        if not auto:
            return

        today = datetime.now().date()
        active_plots = db.query(models.Plot).filter(
            models.Plot.total_due_balance > 0, 
            models.Plot.due_date != None
        ).all()

        for plot in active_plots:
            overdue_days = (today - plot.due_date).days
            
            trigger_type = None
            template_key = None
            log_title = None

            if overdue_days == auto.sms_day and auto.sms_on:
                trigger_type = "SMS"
                template_key = "sms"
                log_title = "SMS Reminder Sent"
            elif overdue_days == auto.wa_day and auto.wa_on:
                trigger_type = "WhatsApp"
                template_key = "whatsapp"
                log_title = "WhatsApp Reminder Sent"
            elif overdue_days == auto.escalate_day and auto.escalate_on:
                trigger_type = "Escalation"
                template_key = "escalate"
                log_title = "Escalated to Staff"

            if trigger_type and template_key:
                # 🔴 TEMPLATE DATABASE SE HI FETCH HO RAHA HAI 🔴
                template = db.query(models.MessageTemplate).filter(models.MessageTemplate.template_key == template_key).first()
                
                if template and template.is_enabled:
                    final_msg = format_message(template.body, plot, profile)
                    client_phone = plot.client.contact_no if plot.client else ""
                    
                    is_sent = False
                    # 🔴 ACTUAL MESSAGE BHEJNE KA LOGIC 🔴
                    if trigger_type == "SMS":
                        is_sent = send_real_sms(client_phone, final_msg)
                    elif trigger_type == "WhatsApp":
                        is_sent = send_real_whatsapp(client_phone, final_msg)
                    elif trigger_type == "Escalation":
                        staff_phone = plot.assigned_staff.phone if plot.assigned_staff else ""
                        is_sent = send_real_whatsapp(staff_phone, final_msg) # Staff ko WhatsApp bhej do
                    
                    # Agar success hua tabhi database me history likho
                    if is_sent or MSG91_AUTH_KEY == "YOUR_MSG91_AUTH_KEY_HERE": 
                        desc = f"Automated {trigger_type} sent. Outstanding: ₹{plot.total_due_balance:,.0f}"
                        if trigger_type == "Escalation":
                            desc = f"Case escalated to {plot.assigned_staff.name if plot.assigned_staff else 'Staff'}."
                            
                        activity = models.ActivityLog(plot_id=plot.id, date=today, title=log_title, description=desc)
                        db.add(activity)
                        
        db.commit()
        print("✅ Daily Automation Complete.")
    except Exception as e:
        print(f"🔥 Error in automation: {e}")
    finally:
        db.close()