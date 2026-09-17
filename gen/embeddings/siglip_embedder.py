from io import BytesIO

import requests


class SiglipEmbedder:
    def __init__(
        self,
        model_name: str = "google/siglip-base-patch16-224",
        device: str | None = None,
    ):
        import torch
        from transformers import AutoModel, AutoProcessor

        self.torch = torch
        self.device = device or ("cuda" if torch.cuda.is_available() else "cpu")
        self.processor = AutoProcessor.from_pretrained(model_name)
        self.model = AutoModel.from_pretrained(model_name).to(self.device)
        self.model.eval()

    def _tensor(self, image):
        inputs = self.processor(images=image, return_tensors="pt").to(self.device)
        with self.torch.no_grad():
            features = self.model.get_image_features(**inputs)
        if not isinstance(features, self.torch.Tensor):
            if getattr(features, "pooler_output", None) is not None:
                features = features.pooler_output
            elif getattr(features, "image_embeds", None) is not None:
                features = features.image_embeds
            elif getattr(features, "last_hidden_state", None) is not None:
                features = features.last_hidden_state.mean(dim=1)
            else:
                features = features[0]
                if len(features.shape) > 2:
                    features = features.mean(dim=1)
        return features / features.norm(dim=-1, keepdim=True)

    def encode_image(self, image) -> list[float]:
        return self._tensor(image)[0].cpu().numpy().tolist()

    def encode_url(self, image_url: str) -> list[float]:
        from PIL import Image

        response = requests.get(image_url, timeout=60)
        response.raise_for_status()
        image = Image.open(BytesIO(response.content)).convert("RGB")
        return self.encode_image(image)
