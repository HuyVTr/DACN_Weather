import torch
import torch.nn as nn
import numpy as np
from torch.cuda.amp import autocast, GradScaler

class FinalTrainer:
    def __init__(self, model):
        self.device = 'cpu'
        self.model = model.to(self.device)
        self.optimizer = torch.optim.AdamW(self.model.parameters(), lr=0.0005)
        self.loss_fn = nn.MSELoss()
        # AMP Scaler
        self.scaler = GradScaler(enabled=(self.device == 'cuda'))
        print(f"🖥️ Device: {self.device.upper()} | AMP Enabled: {self.scaler.is_enabled()}")

    def train_epoch(self, X, y, batch_size=32):
        self.model.train()
        total_loss = 0
        indices = np.random.permutation(len(X))
        for i in range(0, len(X), batch_size):
            batch_idx = indices[i:i+batch_size]
            bx, by = torch.from_numpy(X[batch_idx]).to(self.device), torch.from_numpy(y[batch_idx]).to(self.device)
            
            self.optimizer.zero_grad()
            
            # Use autocast for the forward pass
            with autocast(enabled=self.scaler.is_enabled()):
                outputs = self.model(bx)
                loss = self.loss_fn(outputs['full'], by)

            # Scaler scales the loss and calls backward() to create scaled gradients
            self.scaler.scale(loss).backward()
            
            # Scaler unscales the gradients and calls optimizer.step()
            self.scaler.step(self.optimizer)
            
            # Updates the scale for next iteration
            self.scaler.update()
            
            total_loss += loss.item()
            
        return total_loss / max(1, (len(X) / batch_size))