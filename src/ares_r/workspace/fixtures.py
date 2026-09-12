"""Small deterministic S1A example workspace; not site calibration."""

from .geometry_binding import GeometryBinding
from .occupancy import Occupancy
from .predicates import Predicate, TruthValue
from .relations import Relation, RelationType
from .resource import Container, Holder, Sample, Slot, Station
from .resource_graph import ResourceGraph


def example_workspace() -> ResourceGraph:
    resources = (
        Station("station_1", "Example station"),
        Holder("tray_1", "Example tray", "station_1"),
        Slot("tray_1.slot_3", "Tray slot 3", "tray_1", accepts_occupant_types=("Container",)),
        Container("vial_7", "Example vial"),
        Sample("sample_A", "Example material sample"),
    )
    return ResourceGraph.create(resources,
        relations=(Relation(RelationType.CONTAINS_MATERIAL, "vial_7", "sample_A"),),
        predicates=(Predicate("vial_7", "sealed", TruthValue.FALSE),),
        occupancies=(Occupancy("tray_1.slot_3", "vial_7"),),
        geometry_bindings=(
            GeometryBinding("tray_1", "OBJ_tray_1", "station_1/manipulation", "G1", "C1"),
            GeometryBinding("vial_7", "OBJ_vial_7", "station_1/manipulation", "G1", "C1"),
        ))
