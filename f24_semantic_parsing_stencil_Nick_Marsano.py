# -*- coding: utf-8 -*-
"""Copy of F24 Semantic Parsing Stencil.ipynb

Automatically generated by Colab.

Original file is located at
    https://colab.research.google.com/drive/1z4m-KMWFjlp3SgEWZ2sJpkLeInl5EUoj

# Semantic Parsing Final Project
Link to the paper: https://aclanthology.org/P16-1004.pdf

Read through the paper fully before starting the assignment!
"""

import torch
import torch.nn as nn

from google.colab import drive
drive.mount('/content/drive')

FILEPATH = "/content/drive/MyDrive/Fall 2024/CSCI1460/FP/"

"""# Data Downloading
This cell obtains the pre-processed Jobs dataset (see the paper) that you will be using to train and evaluate your model. (Pre-processed meaning that argument identification, section 3.6, has already been done for you). You should only need to run this cell ***once***. Feel free to delete it after running. Create a folder in your Google Drive in which the code below will store the pre-processed data needed for this project. Modify `FILEPATH` above to direct to said folder. It should start with `drive/MyDrive/...`, feel free to take a look at previous assignments that use mounting Google Drive if you can't remember what it should look like. *Make sure the data path ends with a slash character ('/').* The below code will access the zip file containing the pre-processed Jobs dataset from the paper and extract the files into your folder! Feel free to take a look at the `train.txt` and `test.txt` files to see what the data looks like. :)

# Data Pre-processing
The following code is defined for you! It extracts the queries (inputs to your Seq2Seq model) and logical forms (expected outputs) from the training and testing files. It also does important pre-processing such as padding the queries and logical forms and turns the words into vocab indices. **Look over and understand this code before you start the assignment!**
"""

def extract_file(filename):
  """
  Extracts queries and corresponding logical forms from either
  train.txt or test.txt. (Feel free to take a look at the files themselves
  in your Drive!)

  Parameters
  ----------
  filename : str
      name of the file to extract from

  Returns
  ----------
  tuple[list[list[str]], list[list[str]]]
      a tuple of a list of queries and their corresponding logical forms
      each in the form of a list of string tokens
  """
  queries, logical_forms = [], []
  with open(FILEPATH + filename) as f:
    for line in f:
      line = line.strip() # remove new line character
      query, logical_form = line.split('\t')

      query = query.split(' ')[::-1] # reversed inputs are used the paper (section 4.2)
      logical_form = ["<s>"] + logical_form.split(' ') + ["</s>"]

      queries.append(query)
      logical_forms.append(logical_form)
  return queries, logical_forms

query_train, lf_train = extract_file('train.txt') # 500 instances
query_test, lf_test = extract_file('test.txt') # 140 instances

from collections import Counter

query_vocab = Counter()
for l in query_train:
  query_vocab.update(l)

query_word2idx = {}
for w, c in query_vocab.items():
  if c >= 2:
    query_word2idx[w] = len(query_word2idx)
query_word2idx['<UNK>'] = len(query_word2idx)
query_word2idx['<PAD>'] = len(query_word2idx)
query_idx2word = {i:word for word,i in query_word2idx.items()}

query_vocab = list(query_word2idx.keys())

lf_vocab = Counter()
for lf in lf_train:
  lf_vocab.update(lf)

lf_vocab['<UNK>'] = 0
lf_vocab['<PAD>'] = 0
lf_idx2word = {i:word for i, word in enumerate(lf_vocab.keys())}
lf_word2idx = {word:i for i, word in lf_idx2word.items()}

query_train_tokens = [[query_word2idx.get(w, query_word2idx['<UNK>']) for w in l] for l in query_train]
query_test_tokens = [[query_word2idx.get(w, query_word2idx['<UNK>']) for w in l] for l in query_test]

lf_train_tokens = [[lf_word2idx.get(w, lf_word2idx['<UNK>']) for w in l] for l in lf_train]
lf_test_tokens = [[lf_word2idx.get(w, lf_word2idx['<UNK>']) for w in l] for l in lf_test]

def pad(seq, max_len, pad_token_idx):
  """
  Pads a given sequence to the max length using the given padding token index

  Parameters
  ----------
  seq : list[int]
      sequence in the form of a list of vocab indices
  max_len : int
      length sequence should be padded to
  pad_token_idx
      vocabulary index of the padding token

  Returns
  ----------
  list[int]
      padded sequence
  """
  seq = seq[:max_len]
  padded_seq = seq + (max_len - len(seq)) * [pad_token_idx]
  return padded_seq

query_max_target_len = max([len(i) for i in query_train_tokens])
query_train_tokens = [pad(i, query_max_target_len, query_word2idx['<PAD>']) for i in query_train_tokens]
query_test_tokens = [pad(i, query_max_target_len, query_word2idx['<PAD>']) for i in query_test_tokens]

lf_max_target_len = int(max([len(i) for i in lf_train_tokens]) * 1.5)
lf_train_tokens = [pad(i, lf_max_target_len, lf_word2idx['<PAD>']) for i in lf_train_tokens]
lf_test_tokens = [pad(i, lf_max_target_len, lf_word2idx['<PAD>']) for i in lf_test_tokens]

"""# Data Loading
The following code creates a JobsDataset and DataLoaders to use with your implemented model. Take a look at the main function at the end of this stencil to see how they are used in context.
"""

from torch.utils.data import Dataset, DataLoader, default_collate

class JobsDataset(Dataset):
  """Defines a Dataset object for the Jobs dataset to be used with Dataloader"""
  def __init__(self, queries, logical_forms):
    """
    Initializes a JobsDataset

    Parameters
    ----------
    queries : list[list[int]]
        a list of queries, which have been tokenized and padded, in the form
        of a list of vocab indices
    logical_forms : list[list[int]]
        a list of corresponding logical forms, which have been tokenized and
        padded, in the form of a list of vocab indices
    """
    self.queries = queries
    self.logical_forms = logical_forms

  def __len__(self) -> int:
    """
    Returns the amount of paired queries and logical forms in the dataset

    Returns
    ----------
    int
        length of the dataset
    """
    return len(self.queries)

  def __getitem__(self, idx: int) -> tuple[list[int], list[int]]:
    """
    Returns a paired query and logical form at the specified index

    Parameters
    ----------
    idx : int
        specified index of the dataset

    Returns
    ----------
    tuple[list[int], list[int]]
        paired query and logical form at the specified index, in the form of
        a list of vocab indices
    """
    return self.queries[idx], self.logical_forms[idx]

def build_datasets() -> tuple[JobsDataset, JobsDataset]:
  """
  Builds a train and a test dataset from the queries and logical forms
  train and test tokens

  Returns
  ----------
  tuple[JobsDataset, JobsDataset]
      a training and testing JobsDataset
  """
  jobs_train = JobsDataset(queries=query_train_tokens, logical_forms=lf_train_tokens)
  jobs_test = JobsDataset(queries=query_test_tokens, logical_forms=lf_test_tokens)
  return jobs_train, jobs_test

def collate(batch : list[tuple[list[int], list[int]]]) -> tuple[torch.Tensor, torch.Tensor]:
  """
  Used as collate_fn when creating the Dataloaders from the dataset

  Parameters
  ----------
  batch : list[tuple[list[int], list[int]]]
      a list of outputs of __getitem__

  Returns
  ----------
  tuple[torch.Tensor, torch.Tensor]
      a batched set of input sequences and a batched set of target sequences
  """
  src, tgt = default_collate(batch)
  return torch.stack(src), torch.stack(tgt)

def build_dataloaders(dataset_train: JobsDataset, dataset_test: JobsDataset,
                      train_batch_size: int) -> tuple[DataLoader, DataLoader]:
  """
  Used as collate_fn when creating the Dataloaders from the dataset, batching
  the training data according to the inputted batch size and batching the
  testing data with a batch size of 1

  Parameters
  ----------
  dataset_train : JobsDataset
      training dataset
  dataset_test : JobsDataset
      testing dataset
  train_batch_size : int
      batch size to be used during training

  Returns
  ----------
  tuple[DataLoader, DataLoader]
      a training and testing DataLoader
  """
  dataloader_train = DataLoader(dataset_train, batch_size=train_batch_size, shuffle=True, collate_fn=collate)
  dataloader_test = DataLoader(dataset_test, batch_size=1, shuffle=False, collate_fn=collate)
  return dataloader_train, dataloader_test

"""# TODO: Define your model here!"""

QUERY_VOCAB_LEN = len(query_vocab)
LF_VOCAB_LEN = len(lf_vocab)

class Seq2Seq(nn.Module):
  def __init__(self, query_vocab_len, lf_vocab_len, embedding_dim, hidden_dim, num_layers):
    super(Seq2Seq, self).__init__()

    self.query_embedding = nn.Embedding(query_vocab_len, embedding_dim,padding_idx=query_word2idx['<PAD>'])
    self.lf_embedding = nn.Embedding(lf_vocab_len, embedding_dim,padding_idx=lf_word2idx['<PAD>'])

    self.encoder_lstm = nn.LSTM(embedding_dim, hidden_dim, num_layers, batch_first=True)
    self.decoder_lstm = nn.LSTM(embedding_dim + hidden_dim, hidden_dim, num_layers, batch_first=True)

    self.W1 = nn.Linear(hidden_dim, hidden_dim)  # For h^L_(t)
    self.W2 = nn.Linear(hidden_dim, hidden_dim)  # For c^t
    self.Wo = nn.Linear(hidden_dim, lf_vocab_len)  # For mapping attention-adjusted hidden state to vocab space

  def forward(self, query_seq, lf_seq):
    # Embedding Stage: shapes = (batch_size, seq_len, input_size)
    query_seq = query_seq.transpose(0, 1)
    lf_seq = lf_seq.transpose(0, 1)

    query_embedded = self.query_embedding(query_seq)
    lf_embedded = self.lf_embedding(lf_seq)

    # Create masks for src padding tokens
    src_mask = (query_seq != query_word2idx['<PAD>']).float()  # Mask for query (source) sequence

    # Encoder Stage:
    encoder_output, (encoder_hidden, encoder_cell) = self.encoder_lstm(query_embedded) # hidden_states at timesteps, (final hidden_state, final cell state)

    # Decoder Setup:
    decoder_hidden = encoder_hidden
    decoder_cell = encoder_cell
    decoder_input = lf_embedded[:, 0, :].unsqueeze(1) # Shape: [20, 1, 256]

    outputs = []

    for t in range(0, lf_seq.size(1)):
      # Calculate the context vector via attention:
      decoder_hidden_reshaped = decoder_hidden[-1].unsqueeze(1).squeeze(2)

      # Paper's Equation 5 (attention_scores + attention_weights) (same as softmax)
      attention_scores = torch.matmul(decoder_hidden_reshaped, encoder_output.transpose(1, 2)).squeeze(1) # Shape: [20, 20]
      attention_scores = attention_scores.masked_fill(src_mask == 0, -1e9)  # Apply mask to attention scores (set to very large negative value)

      attention_weights = F.softmax(attention_scores, dim=1) # Shape: [20, 20]

      # Paper's Equation 6
      context_vector = torch.matmul(attention_weights.unsqueeze(1), encoder_output).squeeze(1) # Shape: [20, 1, 256]

      # Paper's Equation 7
      h_att_t = torch.tanh(self.W1(decoder_hidden[-1]) + self.W2(context_vector))

      decoder_input_combined = torch.cat((h_att_t.unsqueeze(1), decoder_input), dim=2)  # Shape: [batch_size, 1, hidden_dim + embedding_dim]

      decoder_output, (decoder_hidden, decoder_cell) = self.decoder_lstm(decoder_input_combined, (decoder_hidden, decoder_cell))

      # A part of Paper's Equation 8 (softmaxxing is done in the train loop)
      logits = self.Wo(h_att_t)  # Shape: [batch_size, lf_vocab_len]
      outputs.append(logits)

      # Using Teacher Forcing
      if t < lf_seq.size(1) - 1:
        decoder_input = lf_embedded[:, t+1, :].unsqueeze(1)

    outputs = torch.stack(outputs, dim=1)
    return outputs


def create_model():
  """
  Returns your model!

  Returns
  ----------
  ???
      your model!
  """
  model = Seq2Seq(
      query_vocab_len=QUERY_VOCAB_LEN,
      lf_vocab_len=LF_VOCAB_LEN,
      embedding_dim=256,
      hidden_dim=256,
      num_layers=2
  )
  return model

"""# TODO: Training loop"""

LF_SOS_INDEX = lf_word2idx['<s>']
LF_EOS_INDEX = lf_word2idx['</s>']
LF_PAD_INDEX = lf_word2idx['<PAD>']

import torch.optim as optim

def train(model: nn.Module, train_dataloader: DataLoader, num_epochs: int=5, device: str="cuda") -> nn.Module:
    """
    Trains your model!

    Parameters
    ----------
    model : nn.Module
        your model!
    train_dataloader : DataLoader
        a dataloader of the training data from build_dataloaders
    num_epochs : int
        number of epochs to train for
    device : str
        device that the model is running on

    Returns
    ----------
    model : nn.Module
        the trained model
    """

    optimizer = optim.Adam(model.parameters(), lr=0.001)
    criterion = nn.NLLLoss(ignore_index=LF_PAD_INDEX) # Target Padding mask built into loss function initialization

    model.to(device)
    model.train()

    for epoch in range(num_epochs):
        epoch_loss = 0.0
        for i, (src, tgt) in enumerate(train_dataloader):
            src = src.to(device)  # Shape: [src_seq_len, batch_size] => [20, 20]
            tgt = tgt.to(device)  # Shape: [tgt_seq_len, batch_size] => [64, 20]

            # Forward pass: Get model output
            output = model(src, tgt)  # Shape: [batch_size, tgt_seq_len, vocab_size]

            # Apply log_softmax to the model output (NLLLoss expects log probabilities)
            output_log_softmax = torch.log_softmax(output, dim=-1)  # Shape: [batch_size, tgt_seq_len, vocab_size]

            # Reshaping tgt and probabilities for NLLLoss
            log_probs_flat = output_log_softmax.reshape(-1, output_log_softmax.size(-1)) # Shape: [1280, 52] (must be [batch_size * tgt_seq_len, vocab_size])
            targets_flat = tgt.transpose(0,1).reshape(-1) # Shape: [1280] (must be [batch_size * tgt_seq_len])

            # Compute loss
            loss = criterion(log_probs_flat, targets_flat)
            epoch_loss += loss.item()

            # Backpropagation
            optimizer.zero_grad()
            loss.backward()
            optimizer.step()

        # Print average loss for the epoch
        print(f"Epoch [{epoch+1}/{num_epochs}] completed, Average Loss: {epoch_loss / len(train_dataloader):.4f}")

    return model

"""# TODO: Testing loop

"""

def evaluate(model: nn.Module, dataloader: DataLoader, device: str="cuda") -> tuple[int, int]:
    """
    Evaluates your model!

    Parameters
    ----------
    model : nn.Module
        your model!
    dataloader : DataLoader
        a dataloader of the testing data from build_dataloaders
    device : str
        device that the model is running on

    Returns
    ----------
    tuple[int, int]
        per-token accuracy and exact_match accuracy
    """
    model.eval()
    per_token_correct = 0
    total_tokens = 0
    exact_matches = 0
    total_sequences = 0

    with torch.no_grad():
        for src, tgt in dataloader:
            src = src.to(device)  # Shape: [src_seq_len, batch_size]
            tgt = tgt.to(device)  # Shape: [tgt_seq_len, batch_size]

            # Forward pass: Get model output
            tgt_seq_len, batch_size = tgt.size()
            output = model(src, tgt)  # Shape: [batch_size, tgt_seq_len, vocab_size]

            # Get the predicted tokens by taking the argmax across the vocabulary dimension
            preds = output.argmax(dim=-1)  # Shape: [batch_size, tgt_seq_len]

            # Only counting non-padding tokens
            tgt_mask = (tgt != LF_PAD_INDEX).float()
            total_tokens += (tgt_mask.sum()).item()

            # Compute accuracy (terminate at <EOS>)
            for b in range(batch_size):#redundant with batch size of 1, but generalizable
                pred_seq = []
                for t in range(tgt_seq_len):
                    pred_token = preds[b, t].item()
                    pred_seq.append(pred_token)
                    #per token accuracy
                    if pred_token == tgt.transpose(0,1)[b,t]:
                      per_token_correct+=1
                    if tgt.transpose(0,1)[b,t] == LF_EOS_INDEX:
                        break
                pred_seq = torch.tensor(pred_seq, device=device)

                # Trim padding from the target sequence (pred sequence built without padding)
                tgt_trimmed = tgt.transpose(0,1)[b, :len(pred_seq)]
                #Exact match accuracy
                if (pred_seq == tgt_trimmed).all():
                    exact_matches += 1
                total_sequences += 1

    # Calculate accuracies
    per_token_accuracy = per_token_correct / total_tokens if total_tokens > 0 else 0
    exact_match_accuracy = exact_matches / total_sequences if total_sequences > 0 else 0

    return per_token_accuracy, exact_match_accuracy

"""# Run this!"""

# torch.manual_seed(47)

def main():
    device = "cuda" if torch.cuda.is_available() else "cpu"
    jobs_train, jobs_test = build_datasets()
    dataloader_train, dataloader_test = build_dataloaders(jobs_train, jobs_test, train_batch_size=20)
    model = create_model()
    model = train(model, dataloader_train, num_epochs=20, device=device)
    test_per_token_accuracy, test_exact_match_accuracy = evaluate(model, dataloader_test, device=device)
    print()
    print(f'Test Per-token Accuracy: {test_per_token_accuracy}')
    print(f'Test Exact-match Accuracy: {test_exact_match_accuracy}')
    return test_per_token_accuracy, test_exact_match_accuracy
main() #comment out if running metrics() below

def metrics(iterations=5):
  per_tokens, exact_matches = [], []
  for i in range(iterations):
    print(f"Iteration {i+1}: {{")
    per_token, exact_match = main()
    per_tokens.append(per_token)
    exact_matches.append(exact_match)
    print("}",end="\n\n")
  per_tokens = torch.tensor(per_tokens)
  exact_matches = torch.tensor(exact_matches)

  if iterations > 1:
    print("Average Per-Token Accuracy:", per_tokens.mean().item())
    print("Standard Deviation:", per_tokens.std().item())
    print("Average Exact-Match Accuracy:", exact_matches.mean().item())
    print("Standard Deviation:", exact_matches.std().item())

metrics()