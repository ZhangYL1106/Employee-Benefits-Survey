import streamlit as st
import pandas as pd
import numpy as np
import random
from io import BytesIO
import json

# ============================================
# Survey Design Engine
# ============================================
class ConjointSurveyDesigner:
    def __init__(self, benefits_list, n_alternatives, n_questions, items_per_alternative):
        self.benefits = benefits_list
        self.n_alternatives = n_alternatives
        self.n_questions = n_questions
        self.items_per_alternative = items_per_alternative
        
    def generate_random_bundle(self, exclude_benefits=set()):
        """Generate a random benefit bundle"""
        available = [b for b in self.benefits if b not in exclude_benefits]
        if len(available) < self.items_per_alternative:
            available = self.benefits.copy()
        return random.sample(available, min(self.items_per_alternative, len(available)))
    
    def generate_question(self, question_id):
        """Generate one choice question"""
        alternatives = []
        used_benefits = set()
        
        for alt_id in range(self.n_alternatives):
            bundle = self.generate_random_bundle(used_benefits)
            alternatives.append({
                'alternative_id': chr(65 + alt_id),  # A, B, C, D
                'benefits': bundle
            })
            used_benefits.update(bundle)
        
        return {
            'question_id': question_id,
            'alternatives': alternatives
        }
    
    def generate_survey(self, n_respondents):
        """Generate surveys for multiple respondents"""
        all_surveys = []
        
        for resp_id in range(1, n_respondents + 1):
            survey = {
                'respondent_id': resp_id,
                'questions': []
            }
            
            for q_id in range(1, self.n_questions + 1):
                question = self.generate_question(q_id)
                survey['questions'].append(question)
            
            all_surveys.append(survey)
        
        return all_surveys
    
    def export_to_csv(self, surveys):
        """Export to CSV format for analysis"""
        rows = []
        
        for survey in surveys:
            resp_id = survey['respondent_id']
            for question in survey['questions']:
                q_id = question['question_id']
                for alt in question['alternatives']:
                    benefit_cols = {f'benefit_{i+1}': alt['benefits'][i] if i < len(alt['benefits']) else '' 
                                   for i in range(self.items_per_alternative)}
                    rows.append({
                        'respondent_id': resp_id,
                        'question_id': q_id,
                        'alternative': alt['alternative_id'],
                        **benefit_cols
                    })
        
        return pd.DataFrame(rows)
    
    def generate_google_forms_template(self, surveys):
        """Generate individual Google Forms templates (one per employee)"""
        forms_data = []
        
        for survey in surveys:
            form_text = f"# Employee Benefits Survey - Employee ID: {survey['respondent_id']}\n\n"
            form_text += "Please select your preferred benefit package for each question.\n\n"
            form_text += "---\n\n"
            
            for question in survey['questions']:
                form_text += f"## Question {question['question_id']}\n"
                form_text += "Which benefit package do you prefer most?\n\n"
                
                for alt in question['alternatives']:
                    form_text += f"- **Option {alt['alternative_id']}**: {' + '.join(alt['benefits'])}\n"
                
                form_text += f"\n*Your answer (A/B/C):* ___________\n\n"
                form_text += "---\n\n"
            
            forms_data.append({
                'respondent_id': survey['respondent_id'],
                'form_content': form_text
            })
        
        return forms_data

# ============================================
# Streamlit App Interface
# ============================================
def main():
    st.set_page_config(page_title="Employee Benefits Survey Designer", layout="wide")
    
    st.title("🎯 Employee Benefits Survey Designer")
    st.markdown("### Design conjoint analysis surveys to understand employee benefit preferences")
    
    # Sidebar - Configuration Panel
    st.sidebar.header("⚙️ Survey Configuration")
    
    # Default benefits list
    default_benefits = [
        "Health Insurance (Medical/Dental/Vision)",
        "401k Matching Plan",
        "Additional Paid Time Off (+5 days)",
        "Remote Work Flexibility",
        "Gym Membership/Fitness Stipend",
        "Learning & Development Budget ($2000/year)",
        "Mental Health Counseling Services",
        "Extended Parental Leave (12 weeks)",
        "Commuter Benefits",
        "Meal Stipend",
        "Stock Options/RSUs",
        "Flexible Work Hours",
        "Pet Insurance",
        "Student Loan Repayment Assistance",
        "Home Office Equipment Stipend",
        "Annual Health Screening",
        "Team Building Activities Budget",
        "Career Mentorship Program",
        "Legal/Financial Advisory Services",
        "Employee Discount Programs"
    ]
    
    # Parameters
    n_employees = st.sidebar.number_input(
        "Number of Employees", 
        min_value=10, 
        max_value=500, 
        value=50, 
        step=10,
        help="Total number of employees to survey"
    )
    
    n_questions = st.sidebar.slider(
        "Questions per Employee", 
        min_value=3, 
        max_value=8, 
        value=4,
        help="Number of questions each employee answers (3-4 recommended for 20 buckets)"
    )
    
    n_alternatives = st.sidebar.slider(
        "Options per Question", 
        min_value=2, 
        max_value=4, 
        value=3,
        help="Number of benefit packages to compare in each question"
    )
    
    items_per_alternative = st.sidebar.slider(
        "Benefits per Package", 
        min_value=1, 
        max_value=4, 
        value=2,
        help="Number of benefits included in each package"
    )
    
    # Benefits list editor
    st.sidebar.markdown("---")
    st.sidebar.subheader("📋 Benefits List")
    
    benefits_text = st.sidebar.text_area(
        "Edit benefits (one per line):",
        value="\n".join(default_benefits),
        height=300
    )
    
    benefits_list = [b.strip() for b in benefits_text.split("\n") if b.strip()]
    
    st.sidebar.info(f"Total benefits: {len(benefits_list)}")
    
    # Main content area
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.markdown("### 📊 Survey Design Summary")
        st.markdown(f"""
        - **Total Employees**: {n_employees}
        - **Questions per Employee**: {n_questions}
        - **Options per Question**: {n_alternatives}
        - **Benefits per Package**: {items_per_alternative}
        - **Total Benefits**: {len(benefits_list)}
        - **Total Survey Responses**: {n_employees * n_questions}
        """)
    
    with col2:
        st.markdown("### 💡 Design Logic")
        st.info(f"""
        Each employee answers only **{n_questions} questions** (low burden).
        
        With **{n_employees} employees**, you'll collect **{n_employees * n_questions} choice observations**.
        
        This is enough to statistically determine preference weights for all {len(benefits_list)} benefits.
        """)
    
    # Generate button
    st.markdown("---")
    if st.button("🚀 Generate Survey Design", type="primary"):
        with st.spinner("Generating survey design..."):
            # Initialize designer
            designer = ConjointSurveyDesigner(
                benefits_list=benefits_list,
                n_alternatives=n_alternatives,
                n_questions=n_questions,
                items_per_alternative=items_per_alternative
            )
            
            # Generate surveys
            surveys = designer.generate_survey(n_employees)
            
            # Export to CSV
            df_design = designer.export_to_csv(surveys)
            
            # Generate Google Forms templates
            forms_data = designer.generate_google_forms_template(surveys)
            
            st.success("✅ Survey design generated successfully!")
            
            # Display preview
            st.markdown("### 📄 Survey Design Preview (First 3 Employees)")
            
            for i, survey in enumerate(surveys[:3]):
                with st.expander(f"Employee ID: {survey['respondent_id']}", expanded=(i==0)):
                    for question in survey['questions']:
                        st.markdown(f"**Question {question['question_id']}**: Which benefit package do you prefer?")
                        for alt in question['alternatives']:
                            st.markdown(f"- **Option {alt['alternative_id']}**: {' + '.join(alt['benefits'])}")
                        st.markdown("")
            
            # Download buttons
            st.markdown("---")
            st.markdown("### 💾 Download Files")
            
            col1, col2, col3 = st.columns(3)
            
            # CSV download
            with col1:
                csv_buffer = BytesIO()
                df_design.to_csv(csv_buffer, index=False, encoding='utf-8-sig')
                csv_buffer.seek(0)
                
                st.download_button(
                    label="📥 Download CSV (for analysis)",
                    data=csv_buffer,
                    file_name="survey_design.csv",
                    mime="text/csv"
                )
            
            # Individual forms download (ZIP would be better, showing text format here)
            with col2:
                # Combine all forms into one text file
                all_forms_text = ""
                for form_data in forms_data:
                    all_forms_text += form_data['form_content'] + "\n\n" + "="*80 + "\n\n"
                
                st.download_button(
                    label=f"📥 Download All Forms Text ({n_employees} employees)",
                    data=all_forms_text,
                    file_name="all_employee_surveys.txt",
                    mime="text/plain"
                )
            
            # JSON download
            with col3:
                json_buffer = BytesIO()
                json_buffer.write(json.dumps(surveys, indent=2).encode('utf-8'))
                json_buffer.seek(0)
                
                st.download_button(
                    label="📥 Download JSON (raw data)",
                    data=json_buffer,
                    file_name="survey_design.json",
                    mime="application/json"
                )
            
            # Statistics
            st.markdown("---")
            st.markdown("### 📈 Design Statistics")
            
            col1, col2 = st.columns(2)
            
            with col1:
                st.markdown("**Coverage Analysis**")
                all_benefits_shown = pd.concat([df_design[f'benefit_{i+1}'] for i in range(items_per_alternative)])
                freq = all_benefits_shown.value_counts()
                st.dataframe(freq.reset_index().rename(columns={'index': 'Benefit', 0: 'Frequency'}))
            
            with col2:
                st.markdown("**Data Preview**")
                st.dataframe(df_design.head(15))
            
            st.markdown("---")
            st.info("""
            **Next Steps:**
            1. Download the CSV file for later analysis
            2. Use the forms text to create surveys in Google Forms/Qualtrics
            3. Distribute surveys to employees (each employee gets their specific questions)
            4. Collect responses and proceed to data analysis
            """)

if __name__ == "__main__":
    main()