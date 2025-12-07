import torch
import torch.nn as nn

class FinalTFT(nn.Module):
    def __init__(self, input_size=10, hidden_size=96, num_heads=6, 
                 num_layers=3, output_size=10, forecast_horizon=168):
        super().__init__()
        self.forecast_horizon = forecast_horizon
        self.input_projection = nn.Linear(input_size, hidden_size)
        self.position_embedding = nn.Embedding(300, hidden_size)
        self.dropout = nn.Dropout(0.15)
        encoder_layer = nn.TransformerEncoderLayer(
            d_model=hidden_size, nhead=num_heads,
            dim_feedforward=hidden_size*3, dropout=0.15,
            batch_first=True, activation='gelu'
        )
        self.encoder = nn.TransformerEncoder(encoder_layer, num_layers=num_layers)
        self.decoder_gru = nn.GRU(
            input_size=hidden_size, hidden_size=hidden_size,
            num_layers=2, batch_first=True, dropout=0.1
        )
        self.output_projection = nn.Linear(hidden_size, output_size)
        
    def forward(self, x):
        batch_size, seq_len, _ = x.shape
        positions = torch.arange(seq_len, device=x.device).unsqueeze(0).expand(batch_size, -1)
        x = self.input_projection(x) + self.position_embedding(positions)
        x = self.dropout(x)
        memory = self.encoder(x)
        context = memory[:, -1:, :].repeat(1, self.forecast_horizon, 1)
        decoded, _ = self.decoder_gru(context)
        return {'full': self.output_projection(decoded)}
