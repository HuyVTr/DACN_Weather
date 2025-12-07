import torch
import torch.nn as nn

class FastTemporalFusionTransformer(nn.Module):
    """
    Mô hình TFT rút gọn:
    - Encoder = TransformerEncoder nhẹ
    - Decoder = GRU
    - Dùng cho bài toán dự báo 7 ngày từ 72 giờ quan sát
    """

    def __init__(self, input_size, hidden_size, num_heads, num_layers, output_size, forecast_horizon):
        super().__init__()
        self.forecast_horizon = forecast_horizon

        # Chiếu input lên hidden_size
        self.input_projection = nn.Linear(input_size, hidden_size)
        self.dropout = nn.Dropout(0.1)

        # Encoder Transformer
        encoder_layer = nn.TransformerEncoderLayer(
            d_model=hidden_size,
            nhead=num_heads,
            dim_feedforward=hidden_size * 2,
            dropout=0.1,
            batch_first=True
        )
        self.encoder = nn.TransformerEncoder(encoder_layer, num_layers=num_layers)

        # Decoder GRU
        self.gru = nn.GRU(hidden_size, hidden_size, num_layers=2, batch_first=True)

        # Chiếu về output_size (6 features)
        self.output_projection = nn.Linear(hidden_size, output_size)

    def forward(self, x):
        x = self.input_projection(x)
        x = self.dropout(x)
        memory = self.encoder(x)

        # Lấy hidden cuối nhân lên horizon
        last_hidden = memory[:, -1:, :].repeat(1, self.forecast_horizon, 1)

        output, _ = self.gru(last_hidden)
        return self.output_projection(output)
