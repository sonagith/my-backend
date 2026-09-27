# Backend/db/models.py
from sqlalchemy import Column, Integer, String, Float, ForeignKey, Date
from sqlalchemy.orm import relationship

from db.database import Base

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True)
    hashed_password = Column(String)

class Client(Base):
    __tablename__ = "clients"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    contact_no = Column(String)
    
    # KYC Fields (Original Names Preserved)
    email = Column(String, nullable=True)
    pan_card = Column(String, nullable=True)
    aadhaar_card = Column(String, nullable=True)
    address = Column(String, nullable=True)
    national_id = Column(String, nullable=True)

    # Ee kotha columns ni add cheyandi
    pan_doc_url = Column(String, nullable=True)
    aadhaar_doc_url = Column(String, nullable=True)
    national_id_doc_url = Column(String, nullable=True)
    
    plots = relationship("Plot", back_populates="client")

class Project(Base):
    __tablename__ = "projects"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    location = Column(String, default="India")
    plotPrefix = Column(String, default="P")
    targetClients = Column(Integer, default=100)
    
    plots = relationship("Plot", back_populates="project")

# --- NAYA TABLE DOCUMENTS KE LIYE ---
class PlotDocument(Base):
    __tablename__ = "plot_documents"
    id = Column(Integer, primary_key=True, index=True)
    plot_id = Column(Integer, ForeignKey("plots.id"))
    document_name = Column(String)  # e.g., "Registry", "Agreement"
    document_url = Column(String)   # Path of the uploaded file
    
    plot = relationship("Plot", back_populates="documents")

class Plot(Base):
    __tablename__ = "plots"
    id = Column(Integer, primary_key=True, index=True)
    plot_no = Column(String, index=True)
    project_id = Column(Integer, ForeignKey("projects.id"))
    client_id = Column(Integer, ForeignKey("clients.id"))
    
    # Dimensions & Rates (Original)
    plot_size_sqmtr = Column(Float, nullable=True)
    plot_size_sqft = Column(Float, nullable=True)
    rate = Column(Float, nullable=True)
    plot_value = Column(Float, nullable=True)
    total_received_amount = Column(Float, default=0.0)
    total_due_balance = Column(Float, default=0.0)
    sale_date = Column(Date, nullable=True)
    booked_by = Column(String, nullable=True)
    last_payment_received = Column(Date, nullable=True)
    payment_percentage = Column(Float, default=0.0)
    commission = Column(Float, default=0.0)
    remarks = Column(String, nullable=True)
    
    # Kundli Data (Original)
    total_dp = Column(Float, default=0.0)
    balance_for_installments = Column(Float, default=0.0)
    monthly_emi = Column(Float, default=0.0)
    total_months_passed = Column(Integer, default=0)
    total_months_left = Column(Integer, default=0)
    amt_needed_current_month = Column(Float, default=0.0)
    amt_due_after_dp = Column(Float, default=0.0)
    due_till_date_amount = Column(Float, default=0.0)
    
    # 🔴 Extra Required Case Details
    due_date = Column(Date, nullable=True)
    survey_number = Column(String, nullable=True)
    facing = Column(String, nullable=True)
    agreement_no = Column(String, nullable=True)
    registration_status = Column(String, default="Pending")
    
    end_date = Column(Date, nullable=True)

    # 🔴 Commission Calculation Fields
    commission_per_sqft = Column(Float, default=0.0)
    total_commission = Column(Float, default=0.0)
    commission_paid_amount = Column(Float, default=0.0)
    commission_balance = Column(Float, default=0.0)
    
    # 🔴 Assigned Staff Link
    assigned_staff_id = Column(Integer, ForeignKey("staff.id"), nullable=True)
    
    # Relationships
    client = relationship("Client", back_populates="plots")
    project = relationship("Project", back_populates="plots")
    payments = relationship("Payment", back_populates="plot")
    assigned_staff = relationship("Staff")
    activities = relationship("ActivityLog", back_populates="plot")
    
    # 🔴 NAYA RELATION DOCUMENTS KE SATH
    documents = relationship("PlotDocument", back_populates="plot", cascade="all, delete-orphan")

    def recalculate_commission(self):
        sqft = self.plot_size_sqft or 0.0
        rate = self.commission_per_sqft or 0.0
        self.total_commission = round(sqft * rate, 2)
        paid = self.commission_paid_amount or 0.0
        self.commission_balance = max(0.0, round(self.total_commission - paid, 2))



class Payment(Base):
    __tablename__ = "payments"
    id = Column(Integer, primary_key=True, index=True)
    plot_id = Column(Integer, ForeignKey("plots.id"))
    
    # Original Fields
    date = Column(Date, nullable=True)
    amount = Column(Float, default=0.0)
    drawn_on = Column(String, nullable=True)
    cheque_no = Column(String, nullable=True)
    ch_date = Column(Date, nullable=True)
    remarks = Column(String, nullable=True)
    due_balance = Column(Float, default=0.0)
    receipt_url = Column(String, nullable=True)

    # Useful additions for Payment receipts / history
    bank_name = Column(String, nullable=True)
    received_date = Column(Date, nullable=True)
    booked_by = Column(String, nullable=True)
    
    plot = relationship("Plot", back_populates="payments")

# 🔴 History aur Timeline track karne ke liye
class ActivityLog(Base):
    __tablename__ = "activity_logs"
    id = Column(Integer, primary_key=True, index=True)
    plot_id = Column(Integer, ForeignKey("plots.id"))
    date = Column(Date, nullable=True)
    title = Column(String)
    description = Column(String)
    
    plot = relationship("Plot", back_populates="activities")

class Integration(Base):
    __tablename__ = "integrations"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String)
    description = Column(String)
    icon = Column(String)
    is_connected = Column(Integer, default=0)

class BusinessProfile(Base):
    __tablename__ = "business_profiles"
    id = Column(Integer, primary_key=True, index=True)
    owner_name = Column(String, default="Ramesh Mehta")
    business_name = Column(String, default="Mehta Realty Group")
    phone_number = Column(String, default="+91 98765 43210")
    industry = Column(String, default="Real Estate — Plot Development")
    gstin = Column(String, default="")
    pan = Column(String, default="")
    city = Column(String, default="Kochi")
    state = Column(String, default="Kerala")
    pin_code = Column(String, default="682001")
    rera_no = Column(String, default="")

    logo_url = Column(String, nullable=True)

class Staff(Base):
    __tablename__ = "staff"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String)
    role = Column(String)
    phone = Column(String)
    email = Column(String, default="staff@gharpilot.in")

class AutomationSettings(Base):
    __tablename__ = "automation_settings"
    id = Column(Integer, primary_key=True, index=True)
    sms_day = Column(Integer, default=11)
    sms_on = Column(Integer, default=1)
    wa_day = Column(Integer, default=13)
    wa_on = Column(Integer, default=1)
    voice_day = Column(Integer, default=15)
    voice_on = Column(Integer, default=1)
    escalate_day = Column(Integer, default=16)
    escalate_on = Column(Integer, default=1)

class MessageTemplate(Base):
    __tablename__ = "message_templates"
    id = Column(Integer, primary_key=True, index=True)
    template_key = Column(String, unique=True, index=True)
    title = Column(String)
    subtitle = Column(String)
    icon = Column(String)
    bg_color = Column(String)
    text_color = Column(String)
    is_enabled = Column(Integer, default=1)
    subject = Column(String)
    body = Column(String)

class PlaceholderRef(Base):
    __tablename__ = "placeholder_refs"
    id = Column(Integer, primary_key=True, index=True)
    ph_key = Column(String, unique=True, index=True)
    description = Column(String)
    sample_value = Column(String)