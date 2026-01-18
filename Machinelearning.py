import pandas as pd

# Load datasets
fake = pd.read_csv("fake.csv")
true = pd.read_csv("true.csv")

# Add labels
fake["label"] = 0   # Fake news
true["label"] = 1   # Real news

# Combine datasets
df = pd.concat([fake, true], axis=0)

# Shuffle data
df = df.sample(frac=1, random_state=42).reset_index(drop=True)

print("Combined dataset loaded")
print(df.head())
print(df.shape)
# Combine title and text
df["content"] = df["title"] + " " + df["text"]

print(df["content"].head())
from sklearn.model_selection import train_test_split

X = df["content"]   # Input text
y = df["label"]     # Output (0 or 1)

X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=0.2, random_state=42
)

print("Training samples:", len(X_train))
print("Testing samples:", len(X_test))
from sklearn.feature_extraction.text import TfidfVectorizer

vectorizer = TfidfVectorizer(
    stop_words="english",
    max_df=0.7
)

X_train_tfidf = vectorizer.fit_transform(X_train)
X_test_tfidf = vectorizer.transform(X_test)

print("Text converted to numbers")
from sklearn.linear_model import LogisticRegression

model = LogisticRegression(max_iter=1000)
model.fit(X_train_tfidf, y_train)

print("Model trained successfully")

from sklearn.metrics import accuracy_score, classification_report

y_pred = model.predict(X_test_tfidf)

print("Accuracy:", accuracy_score(y_test, y_pred))
print(classification_report(y_test, y_pred))
news = ["Government announces new AI education policy"]

news_tfidf = vectorizer.transform(news)
prediction = model.predict(news_tfidf)

print("Prediction:", "REAL" if prediction[0] == 1 else "FAKE")
import pickle

# Save model
with open("fake_news_model.pkl", "wb") as f:
    pickle.dump(model, f)

# Save vectorizer
with open("tfidf_vectorizer.pkl", "wb") as f:
    pickle.dump(vectorizer, f)

print("Model and vectorizer saved")
