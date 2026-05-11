import time
import requests
from typing import Dict, Optional, List, Any, Callable
from dataclasses import dataclass, field
from enum import Enum


class RequestStatus(Enum):
    """Request status enum"""

    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    ALL_COMPLETED_SUCCESSFULLY = "ALL_COMPLETED_SUCCESSFULLY"
    PARTIALLY_COMPLETED = "PARTIALLY_COMPLETED"
    FAILED = "FAILED"


TERMINAL_STATUSES = {
    RequestStatus.COMPLETED,
    RequestStatus.ALL_COMPLETED_SUCCESSFULLY,
    RequestStatus.PARTIALLY_COMPLETED,
    RequestStatus.FAILED,
}


@dataclass
class ReferenceLigandInput:
    """Reference ligand structure input (3D molblock)."""

    id: str
    mol_block: str


@dataclass
class LigandInput:
    """Query ligand input (SMILES)."""

    id: str
    smiles: str

@dataclass
class ProteinInput:
    """Protein structure input (cleaned PDB recommended)."""

    id: str
    mol_block: str

@dataclass
class JobStatus:
    """Status of an individual ligand job within a request."""

    ligand_id: str
    status: str
    reference_ligand_id: str = ""
    batch_job_id: str = ""
    created_at: str = ""
    result: Optional[Dict] = None
    error: Optional[Any] = None
    time_elapsed: Optional[float] = None


@dataclass
class StatusSummary:
    """Aggregate counters returned alongside a request status."""

    total: int
    pending: int
    processing: int
    completed: int
    failed: int
    pending_percent: float
    processing_percent: float
    completed_percent: float
    failed_percent: float
    time_elapsed_total: float


@dataclass
class AsyncRequest:
    """Represents an async prediction request and all its ligand jobs."""

    request_id: str
    batch_job_id: str
    status: RequestStatus
    created_at: str
    total_ligands: int
    jobs: List[JobStatus] = field(default_factory=list)
    status_summary: Optional[StatusSummary] = None


@dataclass
class QuotaInfo:
    """User quota information."""

    user_id: str
    quota_used: int
    quota_remaining: int
    quota_max: int


class Dock3DClient:
    """
    Client for the 3D Dock prediction API.

    Example usage:
        client = Dock3DClient(
            base_url="https://api.example.com/v1",
            api_key="your-api-key",
        )

        quota = client.get_quota()
        print(f"Remaining: {quota.quota_remaining}/{quota.quota_max}")

        protein = ProteinInput(id="my_target", mol_block=open("prot.pdb").read())
        reference = ReferenceLigandInput(id="ref", mol_block=open("ref.sdf").read())
        ligands = [LigandInput(id="lig_0", smiles="CCO")]

        response = client.create_request(
            protein=protein,
            reference_ligand=reference,
            ligands=ligands,
            batch_job_id="run_001",
        )

        result = client.wait_for_completion(
            response["request_id"], check_interval=5
        )
    """

    def __init__(
        self,
        base_url: str,
        api_key: str,
        timeout: int = 300,
        max_retries: int = 3,
        base_sleep: float = 1.0,
    ):
        """
        Initialize the API client.

        Args:
            base_url: Base URL of the API.
            api_key: API key sent as the ``x-api-key`` header.
            timeout: HTTP request timeout in seconds (default: 300).
            max_retries: Number of retries on HTTP 429 (rate limited).
            base_sleep: Base sleep (seconds) between retries; exponential backoff.
        """
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.max_retries = max_retries
        self.base_sleep = base_sleep
        self.session = requests.Session()
        self.session.headers.update({"x-api-key": api_key})


    def _request_with_retry(
        self, method: str, url: str, **kwargs
    ) -> requests.Response:
        """Send an HTTP request with retry on 429 (rate limited)."""
        response = None
        for attempt in range(self.max_retries):
            response = self.session.request(
                method, url, timeout=self.timeout, **kwargs
            )
            if response.status_code != 429:
                return response
            sleep_time = self.base_sleep * (2 ** attempt)
            time.sleep(sleep_time)
        return response

    def _post_request(self, payload: Dict[str, Any]) -> Dict:
        """POST a prediction payload to /requests and return the parsed response."""
        response = self._request_with_retry(
            "POST", f"{self.base_url}/requests", json=payload
        )
        response.raise_for_status()

        return response.json()

    def health_check(self) -> Dict:
        """
        Check API health status

        Returns:
            Dict with status and timestamp
        """
        response = self.session.get(f"{self.base_url}/health", timeout=self.timeout)
        response.raise_for_status()
        return response.json()

    def get_quota(self) -> QuotaInfo:
        """Get current quota information for the user."""
        response = self._request_with_retry("GET", f"{self.base_url}/quota")
        response.raise_for_status()
        data = response.json()
        return QuotaInfo(
            user_id=data["user_id"],
            quota_used=data["quota_used"],
            quota_remaining=data["quota_remaining"],
            quota_max=data["quota_max"],
        )

    def get_request_status(self, request_id: str) -> AsyncRequest:
        """Get the status of a request and all its ligand jobs."""
        response = self._request_with_retry(
            "GET", f"{self.base_url}/requests/{request_id}"
        )
        response.raise_for_status()
        data = response.json()

        jobs = [
            JobStatus(
                ligand_id=j["ligand_id"],
                status=j["status"],
                reference_ligand_id=j.get("reference_ligand_id", ""),
                batch_job_id=j.get("batch_job_id", ""),
                created_at=j.get("created_at", ""),
                result=j.get("result"),
                error=j.get("error"),
                time_elapsed=j.get("time_elapsed"),
            )
            for j in data.get("jobs", [])
        ]

        summary_data = data.get("status_summary")
        status_summary = None
        if summary_data:
            status_summary = StatusSummary(
                total=summary_data.get("total", 0),
                pending=summary_data.get("pending", 0),
                processing=summary_data.get("processing", 0),
                completed=summary_data.get("completed", 0),
                failed=summary_data.get("failed", 0),
                pending_percent=summary_data.get("pending_percent", 0.0),
                processing_percent=summary_data.get("processing_percent", 0.0),
                completed_percent=summary_data.get("completed_percent", 0.0),
                failed_percent=summary_data.get("failed_percent", 0.0),
                time_elapsed_total=summary_data.get("time_elapsed_total", 0.0),
            )

        raw_status = data["status"]
        try:
            parsed_status = RequestStatus(raw_status)
        except ValueError:
            parsed_status = RequestStatus.PENDING

        return AsyncRequest(
            request_id=data["request_id"],
            batch_job_id=data.get("batch_job_id", ""),
            status=parsed_status,
            created_at=data.get("created_at", ""),
            total_ligands=data.get("total_ligands", 0),
            jobs=jobs,
            status_summary=status_summary,
        )

    def wait_for_completion(
        self,
        request_id: str,
        check_interval: int = 5,
        max_wait_time: Optional[int] = None,
        progress_callback: Optional[Callable[[AsyncRequest], None]] = None,
    ) -> AsyncRequest:
        """
        Poll a request until all its ligand jobs are in a terminal state.

        Raises:
            TimeoutError: If ``max_wait_time`` is exceeded.
        """
        start_time = time.time()

        while True:
            request = self.get_request_status(request_id)

            if progress_callback:
                progress_callback(request)

            if request.status in TERMINAL_STATUSES:
                return request

            # Also stop once every job has reached a terminal state,
            # even if the overall status string hasn't caught up yet.
            if request.status_summary is not None:
                s = request.status_summary
                if s.total > 0 and (s.completed + s.failed) >= s.total:
                    return request

            if max_wait_time and (time.time() - start_time) > max_wait_time:
                raise TimeoutError(
                    f"Request {request_id} did not complete within "
                    f"{max_wait_time} seconds"
                )

            time.sleep(check_interval)

    def get_results(self, request_id: str) -> Dict[str, Dict[str, Any]]:
        """
        Get all results for a request, keyed by ligand_id.

        Returns:
            Dict mapping ligand_id to a dict containing status + (data | error)
            + time_elapsed.
        """
        request = self.get_request_status(request_id)

        results: Dict[str, Dict[str, Any]] = {}
        for job in request.jobs:
            if job.status == "COMPLETED" and job.result is not None:
                results[job.ligand_id] = {
                    "status": "COMPLETED",
                    "data": job.result,
                    "time_elapsed": job.time_elapsed,
                }
            elif job.status == "FAILED":
                results[job.ligand_id] = {
                    "status": "FAILED",
                    "error": job.error,
                    "time_elapsed": job.time_elapsed,
                }
            else:
                results[job.ligand_id] = {
                    "status": job.status,
                    "time_elapsed": job.time_elapsed,
                }
        return results

    def clean_protein(self, pdb_block: str) -> str:
        """
        Clean and standardise a protein PDB block.

        Calls POST /clean which normalises atom/residue names, converts non-standard
        amino acids, resolves alternate locations, and renumbers atoms.
        """
        response = self._request_with_retry(
            "POST",
            f"{self.base_url}/clean",
            json={"pdb_block": pdb_block},
        )
        response.raise_for_status()
        return response.json()["pdb_block"]

    def create_request(
        self,
        protein: ProteinInput,
        reference_ligand: ReferenceLigandInput,
        ligands: List[LigandInput],
        batch_job_id: Optional[str] = None,
    ) -> Dict:
        """
        Submit a prediction request: one protein + one reference ligand +
        a list of query ligands (SMILES).
        """
        payload: Dict[str, Any] = {
            "protein": {"id": protein.id, "mol_block": protein.mol_block},
            "reference_ligand": {
                "id": reference_ligand.id,
                "mol_block": reference_ligand.mol_block,
            },
            "ligands": [
                {"id": lig.id, "smiles": lig.smiles} for lig in ligands
            ],
        }
        if batch_job_id:
            payload["batch_job_id"] = batch_job_id

        return self._post_request(payload)


# ----------------------------------------------------------------------
# Helper functions for loading structures from files
# ----------------------------------------------------------------------
def load_pdb_file(filepath: str) -> str:
    """Load PDB file content."""
    with open(filepath, "r") as f:
        return f.read()


def load_molblock_file(filepath: str) -> str:
    """Load molblock/SDF file content."""
    with open(filepath, "r") as f:
        return f.read()
