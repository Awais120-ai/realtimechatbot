import os
import cloudinary

cloudinary.config(
    cloud_name=os.getenv("CLOUDINARY_CLOUD_NAME", "zbjl3qbm"),
    api_key=os.getenv("CLOUDINARY_API_KEY", "832965437621832"),
    api_secret=os.getenv("CLOUDINARY_API_SECRET", "hsc_3apaeb3STCa12LMj1dZvY6U"),
    secure=True,
) 