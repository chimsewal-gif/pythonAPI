import pandas as pd

print("Loading files...")

# 1. Load the Excel file
df_excel = pd.read_excel("all.xlsx", sheet_name="Programmes")
df_excel.columns = [col.strip() for col in df_excel.columns]

df_excel = df_excel.rename(columns={
    "S/N": "SN",
    "Programme": "Program",
    "Duration": "Duration",
    "Programme Code": "Programme_Code",
    "Entry Requirements": "Entry_Requirements",
    "Quota": "Quota"
})

# 2. Your additional 118 programs data
additional_data = [
    ["Environmental Sciences","Bachelor of Science in Town and Regional Planning","full time","non-generic, economic fee","4 years"],
    ["Environmental Sciences","Bachelor of Science (Water Resources Engineering and Management)","full time","upgrading","3 years"],
    ["Environmental Sciences","Bachelor of Science (Water Resources Engineering and Management)","odel","non-generic","4 years"],
    ["Environmental Sciences","Bachelor of Science (Water Resources Engineering and Management)","full time","non-generic, economic fee","4 years"],
    ["Environmental Sciences","Bachelor of Science in Value Chain Agriculture","full time","upgrading","3 years"],
    ["Environmental Sciences","Bachelor of Science in Value Chain Agriculture","full time","non-generic, economic fee","4 years"],
    ["Environmental Sciences","Bachelor of Science in Transformative Community Development","full time","upgrading","3 years"],
    ["Environmental Sciences","Bachelor of Science in Transformative Community Development","full time","non-generic, economic fee","4 years"],
    ["Environmental Sciences","Bachelor of Science (Forestry)","full time","non-generic, economic fee","4 years"],
    ["Environmental Sciences","Bachelor of Science (Fisheries and Aquatic Sciences)","full time","upgrading","4 years"],
    ["Environmental Sciences","Bachelor of Science (Fisheries and Aquatic Sciences)","full-time","upgrading","3 years"],
    ["Environmental Sciences","Bachelor of Science (Fisheries and Aquatic Sciences)","codei","non-generic","4 years"],
    ["Environmental Sciences","Bachelor of Science (Fisheries and Aquatic Sciences)","full time","non-generic, economic fee","4 years"],
    ["Environmental Sciences","Bachelor of Science in Land Surveying","full time","upgrading","4 years"],
    ["Environmental Sciences","Bachelor of Science in Land Surveying","full time","non-generic, economic fee","4 years"],
    ["Environmental Sciences","Bachelor of Science in Estate Management","full time","upgrading","4 years"],
    ["Environmental Sciences","Bachelor of Science in Estate Management","full time","non-generic, economic fee","4 years"],
    ["Environmental Sciences","Bachelor of Science in Town and Regional Planning","full time","upgrading","4 years"],
    ["Environmental Sciences","Bachelor of Science (Forestry)","(2 years entry)","","2 years"],
    ["Environmental Sciences","Bachelor of Science (Forestry)","(3 years entry)","","3 years"],
    ["Environmental Sciences","Bachelor of Science (Forestry)","(4 years entry)","","4 years"],
    ["Environmental Sciences","Bachelor of Arts (Development Studies)","full time","non-generic, economic fee","4 years"],
    ["Tourism, Hospitality and Management","Bachelor of Business (Tourism Management)","full time","upgrading","3 years"],
    ["Tourism, Hospitality and Management","Bachelor of Business (Tourism Management)","weekend","non-generic","4 years"],
    ["Tourism, Hospitality and Management","Bachelor of Hospitality Management","full time","non-generic, economic fee","4 years"],
    ["Tourism, Hospitality and Management","Bachelor of Culinary Arts","full time","upgrading","3 years"],
    ["Tourism, Hospitality and Management","Bachelor of Culinary Arts","full time","non-generic, economic fee","4 years"],
    ["Tourism, Hospitality and Management","Bachelor of Arts (Sports Management)","full time","upgrading","3 years"],
    ["Tourism, Hospitality and Management","Bachelor of Arts (Sports Management)","weekend","non-generic","4 years"],
    ["Tourism, Hospitality and Management","Bachelor of Arts (Sports Management)","odel","non-generic","4 years"],
    ["Tourism, Hospitality and Management","Bachelor of Arts (Sports Management)","odel","upgrading","3 years"],
    ["Tourism, Hospitality and Management","Bachelor of Arts (Sports Management)","full time","non-generic, economic fee","4 years"],
    ["Humanities and Social Sciences","Bachelor of Arts (Communication Studies)","weekend","non-generic","4 years"],
    ["Humanities and Social Sciences","Bachelor of Arts (Communication Studies)","weekend","upgrading","3 years"],
    ["Humanities and Social Sciences","Bachelor of Arts (Communication Studies)","odel","upgrading","3 years"],
    ["Humanities and Social Sciences","Bachelor of Arts (Communication Studies)","full time","non-generic, economic fee","4 years"],
    ["Humanities and Social Sciences","Bachelor of Library and Information Science","weekend","non-generic","4 years"],
    ["Humanities and Social Sciences","Bachelor of Library and Information Science","weekend","upgrading","2 years"],
    ["Humanities and Social Sciences","Bachelor of Library and Information Science","odel","non-generic","4 years"],
    ["Humanities and Social Sciences","Bachelor of Library and Information Science","full time","non-generic, economic fee","4 years"],
    ["Humanities and Social Sciences","Bachelor of Education (Languages)","full time","upgrading","2 years"],
    ["Humanities and Social Sciences","Bachelor of Education (Languages)","full time","upgrading","4 years"],
    ["Humanities and Social Sciences","Bachelor of Education (Languages)","adel","non-generic","4 years"],
    ["Humanities and Social Sciences","Bachelor of Education (Languages)","adel","upgrading","2 years"],
    ["Humanities and Social Sciences","Bachelor of Education (Languages)","adel","upgrading","4 years"],
    ["Humanities and Social Sciences","Bachelor of Education (Languages)","full time","non-generic, economic fee","4 years"],
    ["Humanities and Social Sciences","Bachelor of Arts (Politics and Governance)","full time","non-generic, economic fee","4 years"],
    ["Humanities and Social Sciences","Bachelor of Arts (International Relations and Diplomacy)","full time","non-generic, economic fee","4 years"],
    ["Humanities and Social Sciences","Bachelor of Arts (History and Heritage Studies)","model","upgrading","4 years"],
    ["Humanities and Social Sciences","Bachelor of Arts (History and Heritage Studies)","model","non-generic","4 years"],
    ["Humanities and Social Sciences","Bachelor of Arts (History and Heritage Studies)","full time","non-generic, economic fee","4 years"],
    ["Humanities and Social Sciences","Bachelor of Arts (Theology and Religious Studies)","full time","upgrading","2 years"],
    ["Humanities and Social Sciences","Bachelor of Arts (Theology and Religious Studies)","model","non-generic","4 years"],
    ["Humanities and Social Sciences","Bachelor of Arts (Theology and Religious Studies)","full time","non-generic, economic fee","4 years"],
    ["Humanities and Social Sciences","Bachelor of Arts (Security Studies)","full time","upgrading","4 years"],
    ["Science, Technology and Innovation","Bachelor of Science (Honours) (Renewable Energy Systems Engineering)","full time","upgrading","4 years"],
    ["Science, Technology and Innovation","Bachelor of Science (Honours) (Renewable Energy Systems Engineering)","odel","non-generic","5 years"],
    ["Science, Technology and Innovation","Bachelor of Science (Honours) (Renewable Energy Systems Engineering)","","","4 years"],
    ["Science, Technology and Innovation","Bachelor of Science (Honours) (Renewable Energy Systems Engineering)","","","5 years"],
    ["Science, Technology and Innovation","Bachelor of Science in Information and Communication Technology","","","4 years"],
    ["Science, Technology and Innovation","Bachelor of Science in Information, Communication and Management","","","3 years"],
    ["Science, Technology and Innovation","Bachelor of Science in Data Science","","","4 years"],
    ["Science, Technology and Innovation","Bachelor of Science in Data Sciences","","","4 years"],
    ["Science, Technology and Innovation","Bachelor of Science (Honours) in Physics and Electronics","full time","non-generic","1 year"],
    ["Science, Technology and Innovation","Bachelor of Science (Honours) in Mathematics and Statistics","full time","non-generic","1 year"],
    ["Science, Technology and Innovation","Bachelor of Science (Honours) in Biodiversity Conservation and Management","full time","upgrading","4 years"],
    ["Science, Technology and Innovation","Bachelor of Science (Honours) in Parasitology and Disease Vector Control","full time","upgrading","4 years"],
    ["Science, Technology and Innovation","Bachelor of Science (Honours) Biomedical Laboratory Science","full time","upgrading","3 years"],
    ["Science, Technology and Innovation","Bachelor of Science (Honours) Biomedical Laboratory Science","full time","non-generic, economic fee","4 years"],
    ["Education","Bachelor of Education (Science)","full time","upgrading","4 years"],
    ["Education","Bachelor of Education (Science)","odel","non-generic","4 years"],
    ["Education","Bachelor of Education (Science)","odel","upgrading","2 years"],
    ["Education","Bachelor of Education (Science)","odel","upgrading","4 years"],
    ["Education","Bachelor of Education (Science)","full time","non-generic, economic fee","4 years"],
    ["Education","Bachelor of Education (Science)","full time","upgrading","2 years"],
    ["Education","Bachelor of Education (Arts)","odel","non-generic","4 years"],
    ["Education","Bachelor of Education (Arts)","full time","upgrading","2 years"],
    ["Education","Bachelor of Education (Arts)","full time","upgrading","4 years"],
    ["Education","Bachelor of Education (Arts)","odel","upgrading","2 years"],
    ["Education","Bachelor of Education (Arts)","odel","upgrading","4 years"],
    ["Education","Bachelor of Education (Arts)","full time","non-generic, economic fee","4 years"],
    ["Education","Bachelor of Education (Information and Communication Technology)","full time","upgrading","4 years"],
    ["Education","Bachelor of Education (Information and Communication Technology)","full time","non-generic, economic fee","4 years"],
    ["Education","University Certificate in Education (UCE)","model","non-generic","1 year"],
    ["Health Sciences","Bachelor of Science (Honours) in Optometry","full time","upgrading","3 years"],
    ["Health Sciences","Bachelor of Science (Honours) in Optometry","full-time","non-generic, economic fee","5 years"],
    ["Health Sciences","Bachelor of Science in Nursing and Midwifery","full time","upgrading","3 years"],
    ["Health Sciences","Bachelor of Science in Nursing and Midwifery","full time","non-generic, economic fee","4 years"],
    ["Postgraduate (Masters & PhD)","Master of Education (Educational Leadership and Management)","full time","non-generic","2 years"],
    ["Postgraduate (Masters & PhD)","Master of Science in Forestry and Environmental Management","full time","non-generic","2 years"],
    ["Postgraduate (Masters & PhD)","Master of Science in Geographical Information Systems","full time","non-generic","2 years"],
    ["Postgraduate (Masters & PhD)","Master of Science Urban and Regional Planning","full time","non-generic","2 years"],
    ["Postgraduate (Masters & PhD)","Master of Science in Water Resources Management and Development","full time","non-generic","2 years"],
    ["Postgraduate (Masters & PhD)","Master of Science in Sanitation","full time","non-generic","2 years"],
    ["Postgraduate (Masters & PhD)","Master of Science in Information Theory, Coding and Cryptography","full time","non-generic","2 years"],
    ["Postgraduate (Masters & PhD)","Master of Science in Applied Chemistry","full time","non-generic","2 years"],
    ["Postgraduate (Masters & PhD)","Master of Library and Information Science","odel","non-generic","2 years"],
    ["Postgraduate (Masters & PhD)","Master of Library and Information Science","full time","non-generic","2 years"],
    ["Postgraduate (Masters & PhD)","Master of Arts in Theology and Religious Studies","full time","non-generic","2 years"],
    ["Postgraduate (Masters & PhD)","Master of Arts in African History and Heritage","full time","non-generic","2 years"],
    ["Postgraduate (Masters & PhD)","Master of Tourism and Hospitality Management","full time","non-generic","2 years"],
    ["Postgraduate (Masters & PhD)","Master of Science in Nursing Education (Clinical Teaching)","full time","non-generic","2 years"],
    ["Postgraduate (Masters & PhD)","Master of Science in Fisheries and Aquatic Sciences","full time","non-generic","2 years"],
    ["Postgraduate (Masters & PhD)","Master of Science in Transformative Community Development","full time","non-generic","2 years"],
    ["Postgraduate (Masters & PhD)","Master of Science in Renewable and Sustainable Energy Systems Engineering","full time","non-generic","2 years"],
    ["Postgraduate (Masters & PhD)","Master of Arts in Applied Linguistics (Law Enforcement Discourse)","full time","non-generic","2 years"],
    ["Postgraduate (Masters & PhD)","Master of Education (Teacher Education)","full time","non-generic","2 years"],
    ["Postgraduate (Masters & PhD)","Doctor of Philosophy (PhD) in Fisheries and Aquatic Sciences","full time","non-generic","3 years"],
    ["Postgraduate (Masters & PhD)","Doctor of Philosophy (PhD) in Transformative Community Development","full time","non-generic","3 years"],
    ["Postgraduate (Masters & PhD)","Doctor of Philosophy (PhD) in Applied Chemistry","full time","non-generic","3 years"],
    ["Postgraduate (Masters & PhD)","Doctor of Philosophy (PhD) in Theology and Religious Studies","full time","non-generic","3 years"],
    ["Postgraduate (Masters & PhD)","Doctor of Philosophy (PhD) in Forestry and Environmental Management","full time","non-generic","3 years"],
    ["Postgraduate (Masters & PhD)","Doctor of Philosophy (PhD) in Sanitation","full time","non-generic","3 years"],
    ["Postgraduate (Masters & PhD)","Doctor of Fellowship (PhD) in Water Resources Management and Development","full time","non-generic","3 years"],
    ["Postgraduate (Masters & PhD)","Doctor of Philosophy (PhD) in Information Theory, Coding and Cryptography","full time","non-generic","3 years"],
    ["Postgraduate (Masters & PhD)","Doctor of Philosophy (PhD) in Urban and Regional Planning","full time","non-generic","3 years"],
    ["Diplomas & Certificates","Diploma in Sports Management","model","non-generic","2 years"]
]

df_add = pd.DataFrame(additional_data, columns=["Faculty", "Program", "Mode", "Type", "Duration"])

# 3. Combine both
final_df = pd.concat([df_excel, df_add], ignore_index=True)

# Remove exact duplicate rows if any
final_df = final_df.drop_duplicates(subset=["Program", "Duration"], keep='first')

# Reorder columns nicely
cols = ["SN", "Faculty", "Program", "Duration", "Mode", "Type", "Programme_Code", "Entry_Requirements", "Quota"]
final_df = final_df[[col for col in cols if col in final_df.columns]]

# Save
final_df.to_csv("ALL_PROGRAMS_FINAL.csv", index=False)

with pd.ExcelWriter("ALL_PROGRAMS_FINAL.xlsx", engine='openpyxl') as writer:
    final_df.to_excel(writer, sheet_name="All_Programs", index=False)
    
    # Auto-adjust columns
    ws = writer.sheets["All_Programs"]
    for column in ws.columns:
        max_length = 0
        column_letter = column[0].column_letter
        for cell in column:
            try:
                if len(str(cell.value)) > max_length:
                    max_length = len(str(cell.value))
            except:
                pass
        adjusted = min(max_length + 2, 70)
        ws.column_dimensions[column_letter].width = adjusted

print("🎉 FINAL FILE CREATED SUCCESSFULLY!")
print(f"Total programs: {len(final_df)}")
print("\nFiles saved:")
print("   ✅ ALL_PROGRAMS_FINAL.csv")
print("   ✅ ALL_PROGRAMS_FINAL.xlsx")
