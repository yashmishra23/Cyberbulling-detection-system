# Dataset Upload Folder

Place your cyberbullying dataset file in this folder, for example:

```bash
backend/datasets/cyberbullying.csv
```

The trainer supports CSV, XLSX, XLS, and JSON files.

Recommended columns:

- `text`, `comment`, `message`, `tweet`, or `tweet_text` for the comment text
- `label`, `category`, `class`, `target`, or `cyberbullying_type` for the class label
- optional `sentiment` column

Train the LSTM model with auto-detected columns:

```bash
cd backend
python train.py --dataset datasets/cyberbullying.csv
```

Train with explicit columns:

```bash
cd backend
python train.py --dataset datasets/cyberbullying.csv --text-column tweet_text --label-column cyberbullying_type
```

Train the older sklearn model instead:

```bash
cd backend
python train.py --dataset datasets/cyberbullying.csv --model sklearn
```

After training, start the API:

```bash
python -m uvicorn main:app --reload
```
