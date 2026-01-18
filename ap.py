import streamlit as st
import joblib

# -------------------------------
# Page Configuration (MUST be first)
# -------------------------------
st.set_page_config(
    page_title="Fake News Detection",
    page_icon="📰",
    layout="centered"
)

# -------------------------------
# Load Model & Vectorizer
# -------------------------------

@st.cache_resource
def load_model():
    model = joblib.load("fake_news_model.pkl")
    vectorizer = joblib.load("tfidf_vectorizer.pkl")
    return model, vectorizer



model, vectorizer = load_model()

# -------------------------------
# Header Section
# -------------------------------
st.title("📰 Fake News Detection System")

st.markdown("""
### 🔍 AI-powered news authenticity checker  
This application uses **Machine Learning & NLP** to predict whether a news article is **Fake or Real**.
""")

st.divider()

# -------------------------------
# Input Section
# -------------------------------
news_text = st.text_area(
    "📝 Paste the news article here",
    height=250,
    placeholder="Enter a full news article (paragraph-style text gives best results)..."
)

# -------------------------------
# Predict Button
# -------------------------------
predict_button = st.button("🔍 Predict News")

# -------------------------------
# Prediction Logic
# -------------------------------
data = vectorizer.transform([news_text])
proba = model.predict_proba(data)[0]

fake_conf = proba[0]
real_conf = proba[1]

st.write(f"🔎 REAL confidence: {real_conf*100:.2f}%")
st.write(f"🔎 FAKE confidence: {fake_conf*100:.2f}%")

if real_conf >= 0.65:
    st.success("✅ REAL News")
elif real_conf <= 0.35:
    st.error("🚨 FAKE News")
else:
    st.warning("⚠️ UNCERTAIN — News requires fact-checking")

# -------------------------------
# Sample Text Section
# -------------------------------
st.divider()

st.markdown("### 🧪 Try Sample News")

col1, col2 = st.columns(2)

with col1:
    if st.button("📌 Sample REAL News"):
        st.session_state.sample = (
            "The Government of India announced a new healthcare scheme aimed at "
            "providing free medical treatment to senior citizens across the country."
        )
        st.experimental_rerun()

with col2:
    if st.button("📌 Sample FAKE News"):
        st.session_state.sample = (
            "Aliens secretly met government officials in Delhi last night "
            "to discuss a hidden interplanetary agreement."
        )
        st.experimental_rerun()

if "sample" in st.session_state:
    st.text_area(
        "Sample News Text",
        st.session_state.sample,
        height=150
    )

# -------------------------------
# How It Works Section
# -------------------------------
with st.expander("ℹ️ How does this system work?"):
    st.write("""
    1. The input news text is cleaned and processed.
    2. TF-IDF converts text into numerical features.
    3. A trained Machine Learning model analyzes patterns.
    4. The model predicts whether the news is Fake or Real.
    """)

# -------------------------------
# Disclaimer
# -------------------------------
st.warning("""
⚠️ **Disclaimer**  
This system predicts news authenticity based on linguistic patterns learned from data.
It does **not** verify facts from the internet or real-time sources.
""")

# -------------------------------
# Footer
# -------------------------------
st.divider()

st.markdown("""
Developed by **Arpit Pandey**  
B.Tech – Artificial Intelligence  
""")