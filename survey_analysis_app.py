# survey_analyzer.py
# Run with: streamlit run survey_analyzer.py

import streamlit as st
import pandas as pd
import numpy as np
import sqlite3
from io import BytesIO
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime

# ============================================
# Data Analysis Engine
# ============================================
class ConjointAnalyzer:
    def __init__(self, design_df, response_df):
        """
        Initialize analyzer with design and response data
        
        design_df: CSV from survey designer (respondent_id, question_id, alternative, benefit_1, benefit_2, ...)
        response_df: CSV with employee responses (respondent_id, question_id, chosen_alternative)
        """
        self.design_df = design_df
        self.response_df = response_df
        self.merged_df = None
        self.results_df = None
        
    def merge_data(self):
        """Merge design and response data"""
        # Merge to identify which benefits were chosen vs not chosen
        merged = self.design_df.merge(
            self.response_df,
            on=['respondent_id', 'question_id'],
            how='left'
        )
        
        # Mark if this alternative was chosen
        merged['chosen'] = (merged['alternative'] == merged['chosen_alternative']).astype(int)
        
        self.merged_df = merged
        return merged
    
    def calculate_preference_scores(self):
        """Calculate preference scores using choice frequency method"""
        
        # Get all benefit columns
        benefit_cols = [col for col in self.design_df.columns if col.startswith('benefit_')]
        
        # Reshape data to long format
        data_long = []
        
        for _, row in self.merged_df.iterrows():
            for col in benefit_cols:
                benefit = row[col]
                if pd.notna(benefit) and benefit != '':
                    data_long.append({
                        'benefit': benefit,
                        'chosen': row['chosen'],
                        'respondent_id': row['respondent_id'],
                        'question_id': row['question_id']
                    })
        
        df_long = pd.DataFrame(data_long)
        
        # Calculate metrics for each benefit
        benefit_stats = df_long.groupby('benefit').agg({
            'chosen': ['sum', 'count', 'mean']
        }).reset_index()
        
        benefit_stats.columns = ['benefit', 'times_chosen', 'times_shown', 'choice_rate']
        
        # Calculate utility score (normalized)
        benefit_stats['utility_score'] = (
            (benefit_stats['choice_rate'] - benefit_stats['choice_rate'].mean()) / 
            benefit_stats['choice_rate'].std()
        ) * 100
        
        # Calculate preference percentage
        benefit_stats['preference_pct'] = benefit_stats['choice_rate'] * 100
        
        # Sort by utility score
        benefit_stats = benefit_stats.sort_values('utility_score', ascending=False)
        
        self.results_df = benefit_stats
        return benefit_stats
    
    def calculate_logit_regression(self):
        """
        Advanced: Multinomial Logit Regression
        Requires statsmodels - optional if not installed
        """
        try:
            from statsmodels.discrete.discrete_model import MNLogit
            
            # Get all unique benefits
            all_benefits = []
            benefit_cols = [col for col in self.design_df.columns if col.startswith('benefit_')]
            for col in benefit_cols:
                all_benefits.extend(self.design_df[col].dropna().unique())
            all_benefits = list(set(all_benefits))
            
            # Create binary features for each benefit
            X_list = []
            y_list = []
            
            for _, row in self.merged_df.iterrows():
                features = {benefit: 0 for benefit in all_benefits}
                
                for col in benefit_cols:
                    benefit = row[col]
                    if pd.notna(benefit) and benefit != '':
                        features[benefit] = 1
                
                X_list.append(list(features.values()))
                y_list.append(row['chosen'])
            
            X = pd.DataFrame(X_list, columns=all_benefits)
            y = pd.Series(y_list)
            
            # Fit model
            model = MNLogit(y, X)
            result = model.fit(disp=0)
            
            # Extract coefficients
            logit_results = pd.DataFrame({
                'benefit': all_benefits,
                'coefficient': result.params,
                'p_value': result.pvalues
            }).sort_values('coefficient', ascending=False)
            
            return logit_results
            
        except ImportError:
            st.warning("statsmodels not installed. Using simplified analysis method.")
            return None
    
    def save_to_database(self, db_name='survey_results.db'):
        """Save all data to SQLite database"""
        conn = sqlite3.connect(db_name)
        
        # Save design data
        self.design_df.to_sql('survey_design', conn, if_exists='replace', index=False)
        
        # Save response data
        self.response_df.to_sql('survey_responses', conn, if_exists='replace', index=False)
        
        # Save merged data
        self.merged_df.to_sql('merged_data', conn, if_exists='replace', index=False)
        
        # Save analysis results
        self.results_df.to_sql('preference_scores', conn, if_exists='replace', index=False)
        
        # Add timestamp
        metadata = pd.DataFrame([{
            'analysis_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'total_respondents': self.response_df['respondent_id'].nunique(),
            'total_responses': len(self.response_df)
        }])
        metadata.to_sql('analysis_metadata', conn, if_exists='replace', index=False)
        
        conn.close()
        
        return db_name

# ============================================
# Streamlit App Interface
# ============================================
def main():
    st.set_page_config(page_title="Benefits Survey Analysis", layout="wide")
    
    st.title("📊 Employee Benefits Survey Analysis")
    st.markdown("### Analyze survey results to identify top employee preferences")
    
    # File upload section
    st.markdown("---")
    st.header("1️⃣ Upload Survey Data")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("**Survey Design File** (from survey designer)")
        design_file = st.file_uploader(
            "Upload survey_design.csv",
            type=['csv'],
            key='design',
            help="The CSV file generated from the survey designer app"
        )
    
    with col2:
        st.markdown("**Survey Responses File**")
        response_file = st.file_uploader(
            "Upload survey_responses.csv",
            type=['csv'],
            key='response',
            help="CSV with columns: respondent_id, question_id, chosen_alternative"
        )
        
        st.info("""
        **Response file format:**
        - `respondent_id`: Employee ID
        - `question_id`: Question number
        - `chosen_alternative`: A, B, C, or D
        """)
    
    # Sample response data generator
    with st.expander("📝 Don't have response data? Generate sample data"):
        if design_file is not None:
            if st.button("Generate Sample Responses"):
                design_df = pd.read_csv(design_file)
                
                # Generate random responses
                responses = []
                for resp_id in design_df['respondent_id'].unique():
                    for q_id in design_df[design_df['respondent_id']==resp_id]['question_id'].unique():
                        alternatives = design_df[
                            (design_df['respondent_id']==resp_id) & 
                            (design_df['question_id']==q_id)
                        ]['alternative'].unique()
                        
                        responses.append({
                            'respondent_id': resp_id,
                            'question_id': q_id,
                            'chosen_alternative': np.random.choice(alternatives)
                        })
                
                sample_df = pd.DataFrame(responses)
                
                csv_buffer = BytesIO()
                sample_df.to_csv(csv_buffer, index=False)
                csv_buffer.seek(0)
                
                st.download_button(
                    label="⬇️ Download Sample Responses",
                    data=csv_buffer,
                    file_name="sample_responses.csv",
                    mime="text/csv"
                )
                
                st.success("Sample data generated! Download and use for testing.")
    
    # Analysis section
    if design_file is not None and response_file is not None:
        st.markdown("---")
        st.header("2️⃣ Run Analysis")
        
        if st.button("🚀 Analyze Survey Results", type="primary"):
            with st.spinner("Analyzing survey data..."):
                
                # Load data
                design_df = pd.read_csv(design_file)
                response_df = pd.read_csv(response_file)
                
                # Initialize analyzer
                analyzer = ConjointAnalyzer(design_df, response_df)
                
                # Merge data
                merged_df = analyzer.merge_data()
                
                # Calculate preference scores
                results_df = analyzer.calculate_preference_scores()
                
                # Save to database
                db_file = analyzer.save_to_database()
                
                st.success(f"✅ Analysis complete! Database saved as: {db_file}")
                
                # Display results
                st.markdown("---")
                st.header("3️⃣ Analysis Results")
                
                # Top 10 Benefits
                st.subheader("🏆 Top 10 Most Preferred Benefits")
                
                top_10 = results_df.head(10).copy()
                top_10['rank'] = range(1, len(top_10) + 1)
                
                # Display as styled table
                st.dataframe(
                    top_10[['rank', 'benefit', 'preference_pct', 'utility_score', 'times_chosen', 'times_shown']].style.format({
                        'preference_pct': '{:.2f}%',
                        'utility_score': '{:.2f}',
                        'times_chosen': '{:.0f}',
                        'times_shown': '{:.0f}'
                    }).background_gradient(subset=['utility_score'], cmap='RdYlGn'),
                    use_container_width=True
                )
                
                # Visualizations
                st.markdown("---")
                st.subheader("📈 Visualizations")
                
                col1, col2 = st.columns(2)
                
                with col1:
                    # Bar chart of top 10
                    fig1 = px.bar(
                        top_10,
                        x='preference_pct',
                        y='benefit',
                        orientation='h',
                        title='Top 10 Benefits by Preference Rate',
                        labels={'preference_pct': 'Preference Rate (%)', 'benefit': 'Benefit'},
                        color='preference_pct',
                        color_continuous_scale='Viridis'
                    )
                    fig1.update_layout(yaxis={'categoryorder': 'total ascending'})
                    st.plotly_chart(fig1, use_container_width=True)
                
                with col2:
                    # Utility score chart
                    fig2 = px.bar(
                        top_10,
                        x='utility_score',
                        y='benefit',
                        orientation='h',
                        title='Top 10 Benefits by Utility Score',
                        labels={'utility_score': 'Utility Score', 'benefit': 'Benefit'},
                        color='utility_score',
                        color_continuous_scale='RdYlGn'
                    )
                    fig2.update_layout(yaxis={'categoryorder': 'total ascending'})
                    st.plotly_chart(fig2, use_container_width=True)
                
                # Full results table
                st.markdown("---")
                st.subheader("📋 Complete Results (All Benefits)")
                
                st.dataframe(
                    results_df.style.format({
                        'preference_pct': '{:.2f}%',
                        'utility_score': '{:.2f}',
                        'times_chosen': '{:.0f}',
                        'times_shown': '{:.0f}',
                        'choice_rate': '{:.4f}'
                    }),
                    use_container_width=True
                )
                
                # Statistical summary
                st.markdown("---")
                st.subheader("📊 Statistical Summary")
                
                col1, col2, col3, col4 = st.columns(4)
                
                with col1:
                    st.metric(
                        "Total Respondents",
                        response_df['respondent_id'].nunique()
                    )
                
                with col2:
                    st.metric(
                        "Total Responses",
                        len(response_df)
                    )
                
                with col3:
                    st.metric(
                        "Benefits Analyzed",
                        len(results_df)
                    )
                
                with col4:
                    st.metric(
                        "Avg Choice Rate",
                        f"{results_df['choice_rate'].mean():.2%}"
                    )
                
                # SQL Database preview
                st.markdown("---")
                st.subheader("💾 Database Contents")
                
                conn = sqlite3.connect(db_file)
                
                tab1, tab2, tab3, tab4 = st.tabs(["Preference Scores", "Survey Responses", "Merged Data", "Metadata"])
                
                with tab1:
                    df = pd.read_sql_query("SELECT * FROM preference_scores", conn)
                    st.dataframe(df, use_container_width=True)
                
                with tab2:
                    df = pd.read_sql_query("SELECT * FROM survey_responses LIMIT 100", conn)
                    st.dataframe(df, use_container_width=True)
                
                with tab3:
                    df = pd.read_sql_query("SELECT * FROM merged_data LIMIT 100", conn)
                    st.dataframe(df, use_container_width=True)
                
                with tab4:
                    df = pd.read_sql_query("SELECT * FROM analysis_metadata", conn)
                    st.dataframe(df, use_container_width=True)
                
                conn.close()
                
                # Export section
                st.markdown("---")
                st.header("4️⃣ Export Results")
                
                col1, col2, col3 = st.columns(3)
                
                with col1:
                    # Export top 10 CSV
                    csv_buffer = BytesIO()
                    top_10.to_csv(csv_buffer, index=False)
                    csv_buffer.seek(0)
                    
                    st.download_button(
                        label="📥 Download Top 10 (CSV)",
                        data=csv_buffer,
                        file_name="top_10_benefits.csv",
                        mime="text/csv"
                    )
                
                with col2:
                    # Export full results CSV
                    csv_buffer = BytesIO()
                    results_df.to_csv(csv_buffer, index=False)
                    csv_buffer.seek(0)
                    
                    st.download_button(
                        label="📥 Download All Results (CSV)",
                        data=csv_buffer,
                        file_name="full_analysis_results.csv",
                        mime="text/csv"
                    )
                
                with col3:
                    # Export database
                    with open(db_file, 'rb') as f:
                        st.download_button(
                            label="📥 Download Database (SQLite)",
                            data=f,
                            file_name="survey_results.db",
                            mime="application/x-sqlite3"
                        )
                
                # Interpretation guide
                st.markdown("---")
                st.info("""
                **📖 How to Interpret Results:**
                
                - **Preference Rate (%)**: Percentage of times this benefit was chosen when shown
                - **Utility Score**: Standardized score showing relative preference (higher = more preferred)
                - **Times Chosen**: Raw count of how many times employees selected this benefit
                - **Times Shown**: Total number of times this benefit appeared in survey questions
                
                **Recommendation**: Focus on benefits with high preference rates and utility scores for maximum employee satisfaction.
                """)

if __name__ == "__main__":
    main()