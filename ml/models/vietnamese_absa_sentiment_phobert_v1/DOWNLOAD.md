# Vietnamese ABSA PhoBERT Model

## Git LFS Required

The `model.pt` file (515MB) is stored using **Git LFS** (Large File Storage) due to GitHub's 100MB file size limit.

## First Time Setup

If you're cloning this repository, install Git LFS first:

```bash
# Mac
brew install git-lfs

# Linux
sudo apt install git-lfs

# Windows
# Download from https://git-lfs.github.com/

# Initialize Git LFS
git lfs install

# Clone the repository (LFS files will download automatically)
git clone <repository-url>
```

## Alternative: Train the Model Yourself

```bash
# From project root
./train_vietnamese_stress.sh
```
This will train and save the model to this directory.

## Required Files (Included in Git)
- `config.json` - Model configuration
- `metadata.json` - Training metadata
- `test_results.json` - Evaluation results
- `vocab.txt` - Tokenizer vocabulary
- `*.json` - Other tokenizer configs

## Model Info
- **Architecture**: PhoBERT-base-v2
- **Size**: 515MB
- **Task**: Multi-label ABSA sentiment classification
- **Labels**: 10 Vietnamese mental health aspects
- **Training Data**: r/vozforums stress posts
