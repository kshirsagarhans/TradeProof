from pydantic import BaseModel, Field
from typing import List, Optional

class ContainerInfo(BaseModel):
    container_number: str = ""
    seal_number: str = ""

class BillOfLading(BaseModel):
    bl_number: str = ""
    exporter_name: str = ""
    exporter_address: str = ""
    consignee_name: str = ""
    consignee_address: str = ""
    port_of_loading: str = ""
    port_of_discharge: str = ""
    port_of_final_destination: str = ""
    port_of_loading_lat: Optional[float] = None
    port_of_loading_lon: Optional[float] = None
    port_of_discharge_lat: Optional[float] = None
    port_of_discharge_lon: Optional[float] = None
    shipping_bill_references: List[dict] = Field(default_factory=list)
    # Each entry: {"sb_number": "...", "sb_date": "..."}
    total_packages: Optional[int] = None
    gross_weight: Optional[float] = None
    gross_weight_unit: Optional[str] = None
    containers: List[ContainerInfo] = Field(default_factory=list)
    hs_code: Optional[str] = None
    hs_description: Optional[str] = None
    invoice_number: Optional[str] = None
    invoice_amount: Optional[float] = None
    invoice_currency: Optional[str] = None
    raw_text: Optional[str] = None
    extraction_confidence: Optional[str] = None
