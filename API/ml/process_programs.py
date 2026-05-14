import pandas as pd
import os

# Read the file (it's in the current folder)
df = pd.read_excel("all.xlsx", sheet_name="Programmes")

# Clean column names
df.columns = [col.strip() for col in df.columns]

# Rename columns
df = df.rename(columns={
    "S/N": "SN",
    "Programme": "Program",
    "Duration": "Duration",
    "Programme Code": "Programme_Code",
    "Entry Requirements": "Entry_Requirements",
    "Quota": "Quota"
})

# Function to assign Faculty
def assign_faculty(program):
    if not isinstance(program, str):
        return "Other"
    p = program.lower()
    if any(x in p for x in ["education", "teaching"]):
        return "Education"
    elif any(x in p for x in ["nursing", "midwifery", "optometry"]):
        return "Health Sciences"
    elif any(x in p for x in ["tourism", "hospitality", "culinary", "sports", "culture and heritage"]):
        return "Tourism, Hospitality and Management"
    elif any(x in p for x in ["forestry", "fisheries", "water resources", "estate", "land surveying", "town & regional", "agriculture", "transformative", "value chain"]):
        return "Environmental Sciences"
    elif any(x in p for x in ["renewable", "ict", "information & communication", "data science"]):
        return "Science, Technology and Innovation"
    elif any(x in p for x in ["theology", "history", "politics", "governance", "security", "communication", "library", "development", "international relations"]):
        return "Humanities and Social Sciences"
    else:
        return "Other"

df["Faculty"] = df["Program"].apply(assign_faculty)

# Reorder columns
columns_order = ["SN", "Faculty", "Program", "Duration", "Programme_Code", "Entry_Requirements", "Quota"]
df = df[columns_order]

# Save as CSV
df.to_csv("university_programs_final.csv", index=False)

# Save as formatted Excel
with pd.ExcelWriter("university_programs_final.xlsx", engine='openpyxl') as writer:
    df.to_excel(writer, sheet_name="Programmes", index=False)
    
    # Auto adjust column widths
    worksheet = writer.sheets["Programmes"]
    for column in worksheet.columns:
        max_length = 0
        column_letter = column[0].column_letter
        for cell in column:
            try:
                if len(str(cell.value)) > max_length:
                    max_length = len(str(cell.value))
            except:
                pass
        adjusted_width = min(max_length + 2, 60)
        worksheet.column_dimensions[column_letter].width = adjusted_width

print("✅ SUCCESS! Files generated.")
print(f"Total programs: {len(df)}")
print("\nFiles created:")
print("   • university_programs_final.csv")
print("   • university_programs_final.xlsx")
