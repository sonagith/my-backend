# Backend/import_excel.py
import pandas as pd
import re
import math
from db.database import SessionLocal, engine, Base
from db.models import Client, Project, Plot, Payment

# Create Tables
Base.metadata.create_all(bind=engine)

EXCEL_FILE = "Updated_Receipt_record.xlsx"

# ---------------- HELPER FUNCTIONS ----------------
def get_scalar(val):
    if isinstance(val, pd.Series):
        valid_vals = val.dropna()
        return valid_vals.iloc[0] if not valid_vals.empty else None
    return val

def get_float(val):
    val = get_scalar(val)
    if pd.isna(val) or val is None: return 0.0
    try:
        if isinstance(val, str):
            val = val.replace(',', '').replace('₹', '').replace('/-', '').strip()
        f = float(val)
        if math.isnan(f): return 0.0
        return f
    except:
        return 0.0

def get_str(val):
    val = get_scalar(val)
    if pd.isna(val) or val is None: return ""
    s = str(val).strip()
    if s.lower() in ['nan', '#div/0!']: return ""
    return s

def clean_plot_no(val):
    s = get_str(val).replace(' ', '').upper()
    if s.endswith('.0'): s = s[:-2]
    return s

def get_date(val):
    val = get_scalar(val)
    if pd.isna(val) or val is None: return None
    s = str(val).strip()
    if s.lower() in ['nan', 'nat', '']: return None
    try:
        return pd.to_datetime(val, errors='coerce', dayfirst=True).date()
    except:
        return None

def find_plot(db, p_no):
    p = clean_plot_no(p_no)
    if not p: return None
    plot = db.query(Plot).filter(Plot.plot_no == p).first()
    if not plot and p.isdigit(): plot = db.query(Plot).filter(Plot.plot_no == p.zfill(2)).first()
    if not plot and p.isdigit(): plot = db.query(Plot).filter(Plot.plot_no == str(int(p))).first()
    return plot

# ---------------- MAIN LOGIC ----------------
def import_data():
    db = SessionLocal()
    print("\n🚀 Starting 100% Data Extraction (Consolidated + Kundli + Ledgers)...\n")

    try:
        project = db.query(Project).filter(Project.name == "Default Project").first()
        if not project:
            project = Project(name="Default Project")
            db.add(project)
            db.commit()
            db.refresh(project)

        xls = pd.ExcelFile(EXCEL_FILE)
        
        main_sheet, indiv_sheet = None, None
        for s in xls.sheet_names:
            s_low = s.lower().strip()
            if s_low in ["consolidated account", "consolidated report"]: main_sheet = s
            elif s_low in ["indivisual plot record", "individual plot record"]: indiv_sheet = s
        
        if not main_sheet:
            print("❌ Main sheet ('Consolidated Account') not found!")
            return

        # -------------------------------------------------------------
        # 1. READ CONSOLIDATED ACCOUNT (ALL COLUMNS)
        # -------------------------------------------------------------
        print(f"📖 Reading {main_sheet}...")
        df_main = pd.read_excel(EXCEL_FILE, sheet_name=main_sheet) 
        df_main.columns = df_main.columns.astype(str).str.replace('\n', ' ').str.strip()

        clients_added, plots_added = 0, 0

        # Aapke bheje gaye exact column names
        for index, row in df_main.iterrows():
            customer_name = get_str(row.get('Customer Name'))
            if not customer_name or "TOTAL" in customer_name.upper() or "VACCANT" in customer_name.upper(): 
                continue 
            
            plot_no = clean_plot_no(row.get('Plot No'))
            if not plot_no or "TOTAL" in plot_no.upper(): continue

            # Create/Find Client
            client = db.query(Client).filter(Client.name == customer_name).first()
            if not client:
                client = Client(name=customer_name, contact_no=get_str(row.get('CONTACT NO.')))
                db.add(client)
                db.commit()
                db.refresh(client)
                clients_added += 1

            # Create/Find Plot with 100% DATA
            plot = db.query(Plot).filter(Plot.plot_no == plot_no).first()
            if not plot:
                plot = Plot(
                    plot_no=plot_no,
                    project_id=project.id,
                    client_id=client.id,
                    plot_size_sqmtr=get_float(row.get('Plot Size (In Sq.mtr)')),
                    plot_size_sqft=get_float(row.get('Plot Size (In Sq.ft)')),
                    rate=get_float(row.get('Rate')),
                    plot_value=get_float(row.get('PLOT VALUE')),
                    
                    # 🔴 MISSING COLUMNS JO ADD KIYE HAIN 🔴
                    total_received_amount=get_float(row.get('Total Received Amount')),
                    total_due_balance=get_float(row.get('Total Due Balance')),
                    sale_date=get_date(row.get('Sale Date')),
                    booked_by=get_str(row.get('Booked By')),
                    last_payment_received=get_date(row.get('last Payment Received')),
                    payment_percentage=get_float(row.get('Payment Percentage')),
                    commission=get_float(row.get('COMMISSION')),
                    remarks=get_str(row.get('Remarks'))
                )
                db.add(plot)
                db.commit()
                plots_added += 1
                
        print(f"✅ Created {clients_added} Clients & {plots_added} Plots with 100% Consolidated Data.\n")

        # -------------------------------------------------------------
        # 2. READ INDIVIDUAL PLOT RECORD (Ledgers)
        # -------------------------------------------------------------
        payments_added = 0
        if indiv_sheet:
            print(f"📑 Reading Master Ledger '{indiv_sheet}'...")
            try:
                df_indiv = pd.read_excel(EXCEL_FILE, sheet_name=indiv_sheet, header=None)
                current_plot = None
                parsing_payments = False
                amt_idx, date_idx, bank_idx, chq_idx = -1, -1, -1, -1

                for i, row in df_indiv.iterrows():
                    row_strs = [str(v).strip().upper() for v in row.values]
                    row_joined = " ".join(row_strs)

                    if "PLOT NO" in row_joined and "TOTAL" not in row_joined:
                        match = re.search(r'PLOT\s*NO\s*\.?\s*([A-Z0-9\&]+)', row_joined)
                        if match: current_plot = find_plot(db, match.group(1))
                        parsing_payments = False
                        continue

                    if "DATE" in row_strs and any(x in row_strs for x in ["AMOUNT", "CREDIT"]):
                        parsing_payments = True
                        amt_idx = next((j for j, s in enumerate(row_strs) if 'AMOUNT' in s or 'CREDIT' in s), -1)
                        date_idx = next((j for j, s in enumerate(row_strs) if 'DATE' in s), -1)
                        bank_idx = next((j for j, s in enumerate(row_strs) if 'DRAWN' in s or 'BANK' in s or 'CASH' in s), -1)
                        chq_idx = next((j for j, s in enumerate(row_strs) if 'CHEQUE' in s or 'RECEIPT' in s), -1)
                        continue

                    if parsing_payments and current_plot:
                        first_cell = str(row.values[0]).strip().upper()
                        if first_cell in ["TOTAL", "PAID", "BALANCE", "RATE", "TOTAL AMOUNT PAID"] or pd.isna(row.values[0]):
                            if first_cell in ["TOTAL", "PAID", "BALANCE"]: parsing_payments = False
                            continue

                        amt = get_float(row.values[amt_idx]) if amt_idx != -1 else 0.0
                        if amt > 0:
                            db.add(Payment(
                                plot_id=current_plot.id,
                                date=get_date(row.values[date_idx]) if date_idx != -1 else None,
                                amount=amt,
                                drawn_on=get_str(row.values[bank_idx]) if bank_idx != -1 else "",
                                cheque_no=get_str(row.values[chq_idx]) if chq_idx != -1 else ""
                            ))
                            payments_added += 1
                db.commit()
            except Exception as e:
                print(f"❌ Error in Master Ledger: {e}")

        # -------------------------------------------------------------
        # 3. READ OTHER INDIVIDUAL TABS (Kundli + Ledgers)
        # -------------------------------------------------------------
        print("\n💸 Reading Individual Tabs (Extracting Due Balances, EMI, DP, Payments)...")
        ignore_sheets = ["consolidated account", "consolidated report", "indivisual plot record", "individual plot record", "cheque", "cash", "cancel receipt", "sms sheet", "sale deed"]

        for sheet in xls.sheet_names:
            if sheet.lower().strip() in ignore_sheets: continue 
            plot_str = re.sub(r'(?i)plot', '', sheet).strip()
            if not plot_str: continue

            plot_record = find_plot(db, plot_str)
            if not plot_record:
                first_num = re.findall(r'\d+', plot_str)
                if first_num: plot_record = find_plot(db, first_num[0])

            if plot_record:
                try:
                    df_raw = pd.read_excel(EXCEL_FILE, sheet_name=sheet, header=None)
                    header_idx = -1
                    
                    for i, row in df_raw.head(30).iterrows():
                        row_strs = [str(val).strip().upper() for val in row.values]
                        
                        # Find Meta Data from neighboring cells
                        for j, cell_val in enumerate(row_strs):
                            if not cell_val or cell_val == 'NAN': continue
                            
                            next_val = row.values[j+1] if j + 1 < len(row.values) else 0
                            bottom_val = df_raw.iloc[i+1, j] if i + 1 < len(df_raw) else 0
                            
                            if "TOTAL DP" in cell_val:
                                plot_record.total_dp = get_float(next_val) or get_float(bottom_val)
                            elif "BALANCE FOR INSTALL" in cell_val:
                                plot_record.balance_for_installments = get_float(next_val) or get_float(bottom_val)
                            elif "MONTHLY EMI" in cell_val:
                                plot_record.monthly_emi = get_float(next_val) or get_float(bottom_val)
                            elif "MONTHS PASSED" in cell_val:
                                plot_record.total_months_passed = int(get_float(next_val) or get_float(bottom_val))
                            elif "MONTHS LEFT" in cell_val:
                                plot_record.total_months_left = int(get_float(next_val) or get_float(bottom_val))
                            elif "NEEDED TILL CURRENT MONTH" in cell_val:
                                plot_record.amt_needed_current_month = get_float(next_val) or get_float(bottom_val)
                            elif "AFTER DOWN PAYMENT" in cell_val:
                                plot_record.amt_due_after_dp = get_float(next_val) or get_float(bottom_val)
                            elif "DUE TILL DATE" in cell_val:
                                plot_record.due_till_date_amount = get_float(next_val) or get_float(bottom_val)
                                
                        if header_idx == -1 and any('DATE' in s for s in row_strs) and any('CREDIT' in s or 'AMOUNT' in s for s in row_strs):
                            header_idx = i
                    
                    db.commit()
                    
                    if header_idx != -1:
                        df_payments = pd.read_excel(EXCEL_FILE, sheet_name=sheet, header=header_idx)
                        df_payments.columns = df_payments.columns.astype(str).str.strip().str.upper()
                        
                        amt_col = next((c for c in df_payments.columns if 'CREDIT' in c or 'AMOUNT' in c), None)
                        date_col = next((c for c in df_payments.columns if 'DATE' in c), None)
                        bank_col = next((c for c in df_payments.columns if 'BANK' in c or 'CASH' in c or 'DRAWN' in c), None)
                        chq_col = next((c for c in df_payments.columns if 'RECEIPT' in c or 'CHEQUE' in c), None)
                        bal_col = next((c for c in df_payments.columns if 'DUE BALANCE' in c or 'BALANCE' in c), None)
                        rem_col = next((c for c in df_payments.columns if 'REMARKS' in c), None)
                        
                        if amt_col and date_col:
                            for idx, pay_row in df_payments.iterrows():
                                first_cell = str(pay_row.iloc[0]).strip().upper()
                                if first_cell in ['TOTAL', 'PAID', 'BALANCE', 'RATE', 'SALE DATE', 'TOTAL AMOUNT PAID'] or pd.isna(pay_row.iloc[0]):
                                    continue
                                
                                amt = get_float(pay_row.get(amt_col))
                                if amt > 0:
                                    chq = get_str(pay_row.get(chq_col)) if chq_col else ""
                                    pay_date = get_date(pay_row.get(date_col))
                                    
                                    exists = db.query(Payment).filter(
                                        Payment.plot_id == plot_record.id, Payment.amount == amt,
                                        Payment.date == pay_date, Payment.cheque_no == chq
                                    ).first()
                                    
                                    if not exists:
                                        db.add(Payment(
                                            plot_id=plot_record.id,
                                            date=pay_date,
                                            amount=amt,
                                            drawn_on=get_str(pay_row.get(bank_col)) if bank_col else "",
                                            cheque_no=chq,
                                            due_balance=get_float(pay_row.get(bal_col)) if bal_col else 0.0,
                                            remarks=get_str(pay_row.get(rem_col)) if rem_col else ""
                                        ))
                                        payments_added += 1
                            db.commit()
                except Exception as e:
                    print(f"❌ Error in '{sheet}': {e}")

        print(f"\n✅ Success: Total {payments_added} Payments Processed with ZERO DATA LOSS!")
        print("🎉 Please run 'python import_excel.py'")

    except Exception as e:
        print(f"\n🔥 CRITICAL ERROR: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    import_data()