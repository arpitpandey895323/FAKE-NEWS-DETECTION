import pandas as pd

# -----------------------------
# Load Kaggle datasets
# -----------------------------
true_news = pd.read_csv("True.csv")
fake_news = pd.read_csv("Fake.csv")

# Add labels
true_news["label"] = 1   # REAL
fake_news["label"] = 0   # FAKE

# Use only text column
true_news = true_news[["text", "label"]]
fake_news = fake_news[["text", "label"]]

# Combine Kaggle data
kaggle_data = pd.concat([true_news, fake_news])

print("Kaggle data shape:", kaggle_data.shape)

# -----------------------------
# Load Indian real news (API)
# -----------------------------
indian_news = pd.read_csv("indian_real_news_api.csv")

print("Indian news shape:", indian_news.shape)

# -----------------------------
# Combine all data
# -----------------------------
final_data = pd.concat([kaggle_data, indian_news])

# Shuffle dataset
final_data = final_data.sample(frac=1, random_state=42)

# Save final dataset
final_data.to_csv("final_news_dataset.csv", index=False)

print("✅ Final dataset created")
print("Final dataset shape:", final_data.shape)
