import pandas as pd

# Read the uploaded Excel file
df = pd.read_excel("/home/workdir/attachments/all.xlsx", sheet_name="Programmes")

# Clean column names
df.columns = df.columns.str.strip()

# Rename columns for better readability
df = df.rename(columns={
    "S/N": "SN",
    "Programme": "Program",
    "Duration": "Duration",
    "Programme Code": "Programme_Code",
    "Entry Requirements": "Entry_Requirements",
    "Quota": "Quota"
})

# Add Faculty column (you can edit this mapping later)
def assign_faculty(program):
    program = str(program).lower()
    if any(x in program for x in ["education", "teaching"]):
        return "Education"
    elif any(x in program for x in ["nursing", "optometry", "health"]):
        return "Health Sciences"
    elif any(x in program for x in ["tourism", "hospitality", "culinary", "sports"]):
        return "Tourism, Hospitality and Management"
    elif any(x in program for x in ["forestry", "fisheries", "water", "estate", "land", "agriculture", "environmental"]):
        return "Environmental Sciences"
    elif any(x in program for x in ["ict", "information", "renewable", "physics", "math"]):
        return "Science, Technology and Innovation"
    elif any(x in program for x in ["theology", "history", "politics", "governance", "security", "communication", "library", "development"]):
        return "Humanities and Social Sciences"
    else:
        return "Other"

df["Faculty"] = df["Program"].apply(assign_faculty)

# Reorder columns
columns_order = ["SN", "Faculty", "Program", "Duration", "Programme_Code", "Entry_Requirements", "Quota"]
df = df[columns_order]

# Save files
df.to_csv("university_programs_final.csv", index=False)

with pd.ExcelWriter("university_programs_final.xlsx", engine='openpyxl') as writer:
    df.to_excel(writer, sheet_name="Programmes", index=False)
    
    # Auto-adjust column widths
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

print("✅ Processing Completed!")
print(f"Total programs processed: {len(df)}")
print("�� Files created:")
print("   - university_programs_final.csv")
print("   - university_programs_final.xlsx")
