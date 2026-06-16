from pydantic import BaseModel, Field
from typing import List, Optional
from models.bill_of_lading import ContainerInfo

class ShippingBill(BaseModel):
    sb_number: str = ""
    sb_date: str = ""
    exporter_name: str = ""
    exporter_address: str = ""
    consignee_name: str = ""
    consignee_address: str = ""
    port_of_loading: str = ""
    port_of_discharge: str = ""
    port_of_final_destination: str = ""
    pkg_total: Optional[int] = None
    gross_weight_total: Optional[float] = None
    gross_weight_unit: Optional[str] = None
    containers: List[ContainerInfo] = Field(default_factory=list)
    hs_code: Optional[str] = None
    hs_description: Optional[str] = None
    invoice_number: Optional[str] = None
    invoice_amount: Optional[float] = None
    invoice_currency: Optional[str] = None
    raw_text: Optional[str] = None
    source_filename: Optional[str] = None
