import math

import numpy as np
from pydantic import BaseModel


def clean(obj):
    """Convert numpy/pydantic values into JSON-safe Python types; non-finite floats become None."""
    if isinstance(obj, BaseModel):
        return clean(obj.model_dump())
    if isinstance(obj, dict):
        return {str(k): clean(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple, set)):
        return [clean(v) for v in obj]
    if isinstance(obj, np.generic):
        obj = obj.item()
    if isinstance(obj, float) and not math.isfinite(obj):
        return None
    return obj
