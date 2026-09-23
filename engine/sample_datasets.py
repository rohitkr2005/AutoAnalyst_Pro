"""
AutoAnalyst Pro - Built-in Messy Datasets Generator
Generates realistic, dirty, messy real-world datasets for demonstrating
the full end-to-end data cleaning, EDA, ML, and dashboard capabilities.
"""

import os
import random
import numpy as np
import pandas as pd
from datetime import datetime, timedelta

SAMPLES_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "samples")


def ensure_samples_dir():
    os.makedirs(SAMPLES_DIR, exist_ok=True)


def generate_ecommerce_messy(n_rows=500):
    """
    Generates a realistic messy e-commerce dataset:
    - Inconsistent currencies ($1,250.00, 450 USD, €800)
    - Mixed date formats (YYYY-MM-DD, MM/DD/YYYY, DD-Mon-YYYY)
    - Inconsistent city casings and abbreviations (NY, new york, NEW YORK)
    - Messy percentages and discounts (15%, 0.15, 'None')
    - Outliers (quantity = 9999, negative prices)
    - Implicit nulls ('N/A', '?', 'null', '-', '')
    - Duplicates
    """
    np.random.seed(42)
    random.seed(42)
    
    categories = ["Electronics", "Fashion & Apparel", "Home & Kitchen", "Beauty & Care", "Sports & Fitness", "Books"]
    cities = ["New York", "new york", "NEW YORK", "NY", "  Chicago  ", "chicago", "CHICAGO", 
              "Los Angeles", "los angeles", "LA", "Houston", "houston", "Miami", "miami", "Seattle"]
    payment_methods = ["Credit Card", "credit card", "PayPal", "paypal", "Debit", "Cryptocurrency", "apple pay", "Apple Pay", "N/A"]
    delivery_statuses = ["Delivered", "delivered", "In Transit", "Pending", "Cancelled", "Returned", "UNKNOWN", ""]
    
    base_date = datetime(2023, 1, 1)
    
    records = []
    for i in range(n_rows):
        order_id = f"ORD-{1000 + i}"
        customer_id = f"CUST-{random.randint(100, 350)}" if random.random() > 0.06 else (random.choice(["N/A", "null", "", "?", None]))
        
        # Mixed date formats
        days_offset = random.randint(0, 360)
        dt = base_date + timedelta(days=days_offset)
        date_format_choice = random.choice([1, 2, 3, 4, 5])
        if random.random() < 0.05:
            date_str = random.choice(["2023-99-99", "N/A", "", "null", "-"])
        elif date_format_choice == 1:
            date_str = dt.strftime("%Y-%m-%d")
        elif date_format_choice == 2:
            date_str = dt.strftime("%m/%d/%Y")
        elif date_format_choice == 3:
            date_str = dt.strftime("%d-%b-%Y")
        elif date_format_choice == 4:
            date_str = dt.strftime("%Y/%m/%d %H:%M:%S")
        else:
            date_str = dt.strftime("%b %d, %Y")
            
        category = random.choice(categories) if random.random() > 0.03 else random.choice(["Unknown", "N/A", "", None])
        city = random.choice(cities)
        
        # Quantities with outliers and negative return numbers
        if random.random() < 0.03:
            qty = 9999 # extreme outlier
        elif random.random() < 0.04:
            qty = -1 * random.randint(1, 3) # returned items
        else:
            qty = random.randint(1, 8)
            
        # Unit Price with symbols and units
        raw_price = round(random.uniform(15.0, 750.0), 2)
        if random.random() < 0.04:
            price_str = random.choice(["N/A", "free", "0.00", "null", "?", "$ - "])
        elif random.random() < 0.40:
            price_str = f"${raw_price:,.2f}"
        elif random.random() < 0.65:
            price_str = f"{raw_price} USD"
        elif random.random() < 0.75:
            price_str = f"€{raw_price:.2f}"
        else:
            price_str = str(raw_price)
            
        # Discount with mixed formats
        disc_val = random.choice([0, 0.05, 0.10, 0.15, 0.20, 0.25, 0.30])
        if random.random() < 0.05:
            discount_str = random.choice(["None", "N/A", "", "-", "zero"])
        elif random.random() < 0.5:
            discount_str = f"{int(disc_val * 100)}%"
        else:
            discount_str = str(disc_val)
            
        # Total amount calculation
        clean_p = raw_price if isinstance(raw_price, (int, float)) else 50.0
        tot = clean_p * max(1, qty) * (1 - disc_val)
        if random.random() < 0.03:
            total_str = f"${tot * 100:,.2f}" # typo outlier
        elif random.random() < 0.05:
            total_str = random.choice(["null", "N/A", "", "?"])
        elif random.random() < 0.5:
            total_str = f"${tot:,.2f}"
        else:
            total_str = f"{tot:.2f}"
            
        pay_method = random.choice(payment_methods)
        
        # Customer rating 1-5 with outliers and missing
        if random.random() < 0.08:
            rating = random.choice(["N/A", "null", "?", "", "-"])
        elif random.random() < 0.02:
            rating = random.choice([0, 10, -5]) # invalid range
        else:
            rating = random.choice([1, 2, 3, 4, 5, 4.5, 3.5])
            
        delivery = random.choice(delivery_statuses)
        
        records.append({
            "Order_ID": order_id,
            "Customer_ID": customer_id,
            "Transaction_Date": date_str,
            "Customer_City": city,
            "Product_Category": category,
            "Quantity": qty,
            "Unit_Price": price_str,
            "Discount_Rate": discount_str,
            "Total_Revenue": total_str,
            "Payment_Method": pay_method,
            "Customer_Rating": rating,
            "Delivery_Status": delivery
        })
        
    df = pd.DataFrame(records)
    
    # Inject exact duplicate rows (common in dirty transactional data)
    dup_rows = df.iloc[np.random.choice(len(df), size=18, replace=False)].copy()
    df = pd.concat([df, dup_rows], ignore_index=True)
    
    # Shuffle
    df = df.sample(frac=1.0, random_state=42).reset_index(drop=True)
    
    file_path = os.path.join(SAMPLES_DIR, "ecommerce_messy.csv")
    df.to_csv(file_path, index=False)
    return file_path, df


def generate_healthcare_messy(n_rows=450):
    """
    Messy clinical patient dataset:
    - Blood pressure as strings like '120/80 mmHg' or '145/95'
    - Age with negative numbers, missing values, extreme outliers (e.g. 240)
    - Gender with messy casing ('M', 'Male', 'male', 'F', 'Female')
    - Total charges with symbols and commas
    - Categorical diagnosis with typos
    """
    np.random.seed(101)
    random.seed(101)
    
    genders = ["Male", "male", "M", "MALE", "Female", "female", "F", "FEMALE", "Other", "", "N/A", "?"]
    diagnoses = ["Hypertension", "hypertension", "HYPERTENSION", "Type 2 Diabetes", "diabetes", 
                 "Asthma", "asthma", "Cardiovascular", "Healthy / Checkup", "healthy", "Arthritis", "None"]
    
    records = []
    for i in range(n_rows):
        pid = f"PAT-{2000 + i}"
        
        # Age
        if random.random() < 0.06:
            age = random.choice(["Unknown", "N/A", "", "?", None])
        elif random.random() < 0.02:
            age = random.choice([-2, 195, 230]) # outlier
        else:
            age = random.randint(18, 88)
            
        gender = random.choice(genders)
        
        # Blood pressure
        sys = random.randint(95, 175)
        dia = random.randint(60, 110)
        if random.random() < 0.08:
            bp_str = random.choice(["N/A", "null", "?", "", "pending"])
        elif random.random() < 0.35:
            bp_str = f"{sys}/{dia} mmHg"
        elif random.random() < 0.70:
            bp_str = f"{sys}/{dia}"
        else:
            bp_str = f"Sys: {sys}, Dia: {dia}"
            
        # Cholesterol
        chol = random.randint(130, 310)
        if random.random() < 0.06:
            chol_str = random.choice(["N/A", "missing", ""])
        elif random.random() < 0.5:
            chol_str = f"{chol} mg/dL"
        else:
            chol_str = str(chol)
            
        # Glucose
        glucose = round(random.uniform(70, 220), 1) if random.random() > 0.05 else random.choice(["N/A", "null", ""])
        
        # BMI
        if random.random() < 0.05:
            bmi = random.choice(["N/A", "", "?"])
        elif random.random() < 0.02:
            bmi = 150.5 # outlier
        else:
            bmi = round(random.uniform(18.5, 38.5), 1)
            
        heart_rate = random.randint(55, 115) if random.random() > 0.04 else random.choice(["N/A", 0, ""])
        smoker = random.choice(["Yes", "yes", "YES", "No", "no", "NO", "Former", "1", "0", "N/A"])
        diagnosis = random.choice(diagnoses)
        stay_days = random.randint(1, 14) if random.random() > 0.03 else random.choice(["N/A", -1, 99])
        
        charge = round(random.uniform(1200, 48000), 2)
        if random.random() < 0.04:
            charge_str = random.choice(["$ - ", "free", "N/A", "null"])
        elif random.random() < 0.6:
            charge_str = f"${charge:,.2f}"
        else:
            charge_str = str(charge)
            
        records.append({
            "Patient_ID": pid,
            "Age": age,
            "Gender": gender,
            "Blood_Pressure": bp_str,
            "Cholesterol_Level": chol_str,
            "Fasting_Glucose": glucose,
            "BMI": bmi,
            "Resting_Heart_Rate": heart_rate,
            "Smoking_Status": smoker,
            "Primary_Diagnosis": diagnosis,
            "Hospital_Stay_Days": stay_days,
            "Total_Charges": charge_str
        })
        
    df = pd.DataFrame(records)
    
    # Add duplicate records
    dup_rows = df.iloc[np.random.choice(len(df), size=12, replace=False)].copy()
    df = pd.concat([df, dup_rows], ignore_index=True)
    df = df.sample(frac=1.0, random_state=101).reset_index(drop=True)
    
    file_path = os.path.join(SAMPLES_DIR, "healthcare_clinical_messy.csv")
    df.to_csv(file_path, index=False)
    return file_path, df


def generate_saas_messy(n_rows=400):
    """
    Messy SaaS subscription and churn dataset:
    - MRR with symbols ($1,299, 450 USD)
    - Plan tiers with inconsistent casing (PRO, pro, Pro, ENTERPRISE)
    - Mixed churn indicators (True, 1, yes, false, 0)
    - Missing metrics and dates
    """
    np.random.seed(202)
    random.seed(202)
    
    tiers = ["Starter", "starter", "STARTER", "Professional", "pro", "PRO", "Professional Plan", 
             "Enterprise", "enterprise", "ENTERPRISE", "Free Trial", "trial", "N/A"]
    industries = ["Fintech", "Healthtech", "E-commerce", "Edtech", "Logistics", "Marketing", "Cybersecurity", "Other", ""]
    churn_options = ["Yes", "yes", "Y", "True", "true", "1", "No", "no", "N", "False", "false", "0", "N/A", ""]
    
    base_date = datetime(2022, 6, 1)
    records = []
    for i in range(n_rows):
        acc_id = f"SAAS-{5000 + i}"
        company = f"Corp_{random.randint(10, 999)} Inc"
        tier = random.choice(tiers)
        industry = random.choice(industries)
        
        # Signup Date
        dt = base_date + timedelta(days=random.randint(0, 500))
        date_str = dt.strftime("%Y-%m-%d") if random.random() > 0.05 else random.choice(["0000-00-00", "N/A", ""])
        
        # Monthly Recurring Revenue (MRR)
        base_mrr = random.choice([49, 99, 299, 499, 1200, 2400, 4800, 9500])
        mrr_val = base_mrr + round(random.uniform(-10, 50), 2)
        if random.random() < 0.04:
            mrr_str = random.choice(["$0", "N/A", "pending", ""])
        elif random.random() < 0.5:
            mrr_str = f"${mrr_val:,.2f}"
        elif random.random() < 0.8:
            mrr_str = f"{mrr_val} USD"
        else:
            mrr_str = str(mrr_val)
            
        users = random.randint(1, 150) if random.random() > 0.04 else random.choice(["N/A", -1, 9999])
        storage_gb = round(random.uniform(5, 500), 1) if random.random() > 0.05 else random.choice(["null", ""])
        tickets = random.randint(0, 25) if random.random() > 0.03 else random.choice(["N/A", "?"])
        nps = random.randint(1, 10) if random.random() > 0.08 else random.choice(["N/A", -1, 99])
        churn = random.choice(churn_options)
        satisfaction = round(random.uniform(1.0, 5.0), 1) if random.random() > 0.06 else random.choice(["N/A", ""])
        
        records.append({
            "Account_ID": acc_id,
            "Company_Name": company,
            "Subscription_Tier": tier,
            "Industry_Sector": industry,
            "Signup_Date": date_str,
            "Monthly_Revenue_MRR": mrr_str,
            "Active_User_Seats": users,
            "Cloud_Storage_GB": storage_gb,
            "Support_Tickets_Opened": tickets,
            "Net_Promoter_Score": nps,
            "Customer_Churned": churn,
            "Product_Satisfaction": satisfaction
        })
        
    df = pd.DataFrame(records)
    # Add duplicates
    dup_rows = df.iloc[np.random.choice(len(df), size=10, replace=False)].copy()
    df = pd.concat([df, dup_rows], ignore_index=True)
    df = df.sample(frac=1.0, random_state=202).reset_index(drop=True)
    
    file_path = os.path.join(SAMPLES_DIR, "saas_subscriptions_messy.csv")
    df.to_csv(file_path, index=False)
    return file_path, df


def generate_real_estate_messy(n_rows=400):
    """
    Messy real estate housing market dataset:
    - Prices with commas, $, and suffixes
    - Square footage with 'sqft' string
    - Neighborhoods with whitespace and abbreviations
    - Missing year built, bedrooms, bathrooms
    """
    np.random.seed(303)
    random.seed(303)
    
    neighborhoods = ["Downtown", "downtown", "DOWNTOWN", "Westside", "westside", "  Midtown  ", 
                     "midtown", "Suburbs North", "East End", "east end", "Lakeside", "lakeside", "N/A", ""]
    prop_types = ["Single Family", "single family", "Condo", "condo", "Townhouse", "townhouse", "Duplex", "Penthouse", ""]
    
    records = []
    for i in range(n_rows):
        prop_id = f"PROP-{8000 + i}"
        neigh = random.choice(neighborhoods)
        ptype = random.choice(prop_types)
        beds = random.choice([1, 2, 3, 4, 5, "N/A", "", -1]) if random.random() < 0.08 else random.randint(1, 5)
        baths = random.choice([1.0, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0, "N/A"]) if random.random() < 0.07 else round(random.choice([1, 1.5, 2, 2.5, 3, 3.5]), 1)
        
        # Square feet
        sqft_raw = random.randint(650, 4800)
        if random.random() < 0.05:
            sqft_str = random.choice(["N/A", "null", "?", ""])
        elif random.random() < 0.4:
            sqft_str = f"{sqft_raw} sqft"
        elif random.random() < 0.7:
            sqft_str = f"{sqft_raw:,} SQ FT"
        else:
            sqft_str = str(sqft_raw)
            
        yr = random.randint(1950, 2024) if random.random() > 0.06 else random.choice(["N/A", 1800, "unknown"])
        
        # Price
        base_price = (sqft_raw * random.uniform(220, 520)) + (float(beds if isinstance(beds, (int, float)) and beds > 0 else 2) * 25000)
        price_val = round(base_price, -2)
        if random.random() < 0.04:
            price_str = random.choice(["N/A", "$0", "call for price", "null"])
        elif random.random() < 0.5:
            price_str = f"${price_val:,.0f}"
        elif random.random() < 0.75:
            price_str = f"{price_val:,.0f} USD"
        else:
            price_str = str(price_val)
            
        dom = random.randint(1, 180) if random.random() > 0.05 else random.choice(["N/A", -5, 999])
        garage = random.choice([0, 1, 2, 3, "N/A", "None"])
        
        records.append({
            "Property_ID": prop_id,
            "Neighborhood": neigh,
            "Property_Type": ptype,
            "Bedrooms": beds,
            "Bathrooms": baths,
            "Living_Area_SqFt": sqft_str,
            "Year_Built": yr,
            "Listing_Price": price_str,
            "Days_On_Market": dom,
            "Garage_Capacity": garage
        })
        
    df = pd.DataFrame(records)
    dup_rows = df.iloc[np.random.choice(len(df), size=8, replace=False)].copy()
    df = pd.concat([df, dup_rows], ignore_index=True)
    df = df.sample(frac=1.0, random_state=303).reset_index(drop=True)
    
    file_path = os.path.join(SAMPLES_DIR, "real_estate_messy.csv")
    df.to_csv(file_path, index=False)
    return file_path, df


def init_all_samples():
    ensure_samples_dir()
    datasets = {
        "ecommerce": {
            "name": "E-Commerce Omnichannel (Transactions & Customers)",
            "description": "Dirty sales records with currency symbols, mixed date formats, casing variations, negative returns, and nulls.",
            "file": generate_ecommerce_messy()[0]
        },
        "healthcare": {
            "name": "Clinical Patient Records & Diagnostics",
            "description": "Healthcare patient vitals with composite blood pressures ('120/80 mmHg'), age outliers, and missing lab tests.",
            "file": generate_healthcare_messy()[0]
        },
        "saas": {
            "name": "SaaS Subscriptions & Customer Churn",
            "description": "B2B SaaS metric logs with inconsistent plan names, formatted MRR ($1,299), mixed churn booleans, and NPS gaps.",
            "file": generate_saas_messy()[0]
        },
        "real_estate": {
            "name": "Residential Housing Market & Pricing",
            "description": "Property listings with '$' and 'sqft' string values, inconsistent neighborhood casing, and missing spec attributes.",
            "file": generate_real_estate_messy()[0]
        }
    }
    return datasets


if __name__ == "__main__":
    init_all_samples()
    print("All sample datasets successfully generated in samples/ directory.")
