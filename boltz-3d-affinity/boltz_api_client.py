"""
Python Client Example for Async API - Protein-Ligand Predictions

This module provides a Python client to interact with the async protein-ligand prediction API.
Supports prediction of one protein with multiple ligands in parallel.
"""

import os
import time
import requests
from typing import Dict, Optional, List, Any, Callable
from dataclasses import dataclass, field
from enum import Enum
import json


class RequestStatus(Enum):
    """Request status enum"""

    PENDING_UPLOAD = "PENDING_UPLOAD"  # Payload uploaded to S3, waiting for processing
    PENDING = "PENDING"
    STARTING = "STARTING"  # Batch job submitted, container not yet running
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


@dataclass
class ProteinInput:
    """Protein structure input"""

    name: str
    pdb_block: str
    msa_filenames: List[Optional[str]] = field(default_factory=list)
    """
    One MSA filename per protein chain, as returned by upload_msa().
    Leave empty to run without MSA (faster, lower accuracy).
    Use None for a specific chain to skip MSA for that chain only.
    Example (single-chain protein with MSA):
        msa_filenames=["chain_A.csv"]
    Example (two-chain, first with MSA, second without):
        msa_filenames=["chain_A.csv", None]
    """


@dataclass
class LigandInput:
    """Ligand structure input"""

    name: str
    molblock: str


@dataclass
class LigandStatus:
    """Status of an individual ligand prediction"""

    job_name: str
    request_id: str
    status: str
    protein_name: str
    ligand_name: str
    created_at: str
    updated_at: str
    progress: Optional[int] = None
    result: Optional[Dict] = None
    error: Optional[Dict] = None


@dataclass
class StatusSummary:
    """Summary of all ligand prediction statuses"""

    total: int
    pending_upload: int
    pending: int
    starting: int
    processing: int
    completed: int
    failed: int
    pending_upload_percent: float
    pending_percent: float
    starting_percent: float
    processing_percent: float
    completed_percent: float
    failed_percent: float


@dataclass
class AsyncRequest:
    """Represents an async prediction request"""

    parent_request_id: str
    status: RequestStatus
    created_at: str
    updated_at: str
    total_ligands: int
    ligands: List[LigandStatus] = field(default_factory=list)
    status_summary: Optional[StatusSummary] = None


@dataclass
class QuotaInfo:
    """User quota information"""

    user_id: str
    quota_used: int
    quota_remaining: int
    quota_max: int


class AsyncApiClient:
    """
    Client for interacting with the Async Protein-Ligand Prediction API

    Example usage:
        client = AsyncApiClient(
            base_url="https://your-api-url.amazonaws.com/v1",
            user_id="your-user-id",
            api_token="your-bearer-token"
        )

        # Check quota
        quota = client.get_quota()
        print(f"Remaining: {quota.quota_remaining}/{quota.quota_max}")

        # Create a prediction request (one protein, multiple ligands)
        protein = ProteinInput(
            name="kinase_target",
            pdb_block="ATOM      1  N   MET A   1..."
        )
        ligands = [
            LigandInput(name="compound_1", molblock="..."),
            LigandInput(name="compound_2", molblock="..."),
        ]

        response = client.create_request(
            job_name="my_screening_job",
            protein=protein,
            ligands=ligands
        )

        # Wait for completion
        result = client.wait_for_completion(
            response["parent_request_id"],
            check_interval=10
        )
    """

    def __init__(self, base_url: str, api_key: str, timeout: int = 300):
        """
        Initialize the API client

        Args:
            base_url: Base URL of the API (e.g., "https://api.example.com/v1")
            user_id: User identifier for quota tracking and authentication
            api_token: Bearer token for API authentication
            timeout: Request timeout in seconds (default: 300)
        """
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update(
            {
                "x-api-key": api_key,
            }
        )

    @staticmethod
    def _raise_for_status(response: requests.Response) -> None:
        """Call raise_for_status; on failure print URL, status, and body first."""
        if not response.ok:
            print(
                f"HTTP {response.status_code} {response.reason} for {response.url}",
                flush=True,
            )
            try:
                err = response.json()
                print(json.dumps(err, indent=2)[:8000], flush=True)
            except ValueError:
                text = response.text or ""
                tail = "\n... (truncated)" if len(text) > 8000 else ""
                print(f"{text[:8000]}{tail}", flush=True)
        response.raise_for_status()

    def health_check(self) -> Dict:
        """
        Check API health status

        Returns:
            Dict with status and timestamp
        """
        response = self.session.get(f"{self.base_url}/health", timeout=self.timeout)
        self._raise_for_status(response)
        return response.json()

    def get_quota(self) -> QuotaInfo:
        """
        Get current quota information for the user

        Returns:
            QuotaInfo object with usage details and rate limit information

        Example:
            quota = client.get_quota()
            print(f"Used: {quota.quota_used}/{quota.quota_max}")
            print(f"Remaining: {quota.quota_remaining}")
            print(f"Resets at: {quota.reset_at}")
        """
        response = self.session.get(f"{self.base_url}/quota", timeout=self.timeout)
        self._raise_for_status(response)
        data = response.json()

        return QuotaInfo(
            user_id=data["user_id"],
            quota_used=data["quota_used"],
            quota_remaining=data["quota_remaining"],
            quota_max=data["quota_max"],
        )

    def request_msa_upload(self, filename: str) -> Dict:
        """
        Request a presigned S3 POST URL to upload an MSA file.

        Args:
            filename: Original filename of the MSA CSV file (e.g. "chain_A.csv").

        Returns:
            Dict with keys:
                upload_url    – presigned S3 POST URL (target for multipart/form-data POST)
                upload_fields – form fields to include before the file part
                msa_filename  – filename to pass in protein.msa_filenames when creating a request
                expires_in    – seconds until the URL expires
        """
        response = self.session.post(
            f"{self.base_url}/upload/msa",
            json={"filename": filename},
            timeout=self.timeout,
        )
        self._raise_for_status(response)
        return response.json()

    def upload_msa(self, filepath: str) -> str:
        """
        Upload an MSA CSV file to S3 via a presigned POST URL.

        This is a two-step operation:
          1. Call POST /upload/msa to obtain a presigned POST URL, form fields, and a filename.
          2. POST the file as multipart/form-data directly to S3 (no API bandwidth consumed).
             Content-Type is enforced as text/csv and max size is 20 MB.

        Args:
            filepath: Local path to the MSA CSV file.

        Returns:
            msa_filename – the filename to pass in protein.msa_filenames when creating a request.

        Example:
            msa_filename = client.upload_msa("./data/acsl_A.csv")
            protein = ProteinInput(
                name="ACSL",
                pdb_block=load_pdb_file("./data/protein_ACSL.pdb"),
                msa_filenames=[msa_filename],  # one filename per protein chain
            )
        """
        filename = os.path.basename(filepath)
        upload_info = self.request_msa_upload(filename)

        with open(filepath, "rb") as f:
            post_response = requests.post(
                upload_info["upload_url"],
                data=upload_info["upload_fields"],
                files={"file": (filename, f, "text/csv")},
                timeout=self.timeout,
            )
        self._raise_for_status(post_response)

        print(f"MSA uploaded: {filepath} -> s3 key: {upload_info['msa_filename']}")
        return upload_info["msa_filename"]

    def request_payload_upload(self, job_name: str) -> Dict:
        """
        Request a presigned S3 POST URL to upload a prediction payload.

        Call this first to obtain the upload URL, form fields, and a pre-assigned
        parent_request_id. Then pass the result to upload_payload_file().

        Args:
            job_name: Human-readable name for the prediction run.

        Returns:
            Dict with keys:
                upload_url       – presigned S3 POST URL
                upload_fields    – form fields to include before the file part
                parent_request_id – ID to poll with GET /requests/{id}
                expires_in       – seconds until the URL expires
        """
        response = self.session.post(
            f"{self.base_url}/requests/from-payload",
            json={"job_name": job_name},
            timeout=self.timeout,
        )
        self._raise_for_status(response)
        return response.json()

    def upload_payload_file(
        self,
        upload_info: Dict,
        protein: "ProteinInput",
        ligands: "List[LigandInput]",
        cofactors_ions: "Optional[List[LigandInput]]" = None,
        local_filepath: Optional[str] = None,
    ) -> str:
        """
        Serialize and upload a prediction payload directly to S3 via a presigned POST URL.

        The API processes the uploaded file automatically via an S3 trigger —
        no further API call is needed after this.

        Args:
            upload_info:     Dict returned by request_payload_upload() containing
                             upload_url, upload_fields, and parent_request_id.
            protein:         ProteinInput (name, pdb_block, optional msa_filenames).
            ligands:         List of LigandInput.
            cofactors_ions:  Optional list of cofactor/ion LigandInput.
            local_filepath:  Optional local path to save the payload JSON before uploading.

        Returns:
            parent_request_id – use with GET /requests/{parent_request_id} to poll status.
        """
        if cofactors_ions is None:
            cofactors_ions = []

        payload = {
            "job_name": upload_info["job_name"],
            "protein": {
                "name": protein.name,
                "pdb_block": protein.pdb_block,
                "msa_filenames": protein.msa_filenames,
            },
            "ligands": [
                {"name": lig.name, "molblock": lig.molblock} for lig in ligands
            ],
            "cofactors_ions": [
                {"name": c.name, "molblock": c.molblock} for c in cofactors_ions
            ],
        }

        payload_json = json.dumps(payload, indent=2)

        if local_filepath:
            with open(local_filepath, "w") as f:
                f.write(payload_json)

        post_response = requests.post(
            upload_info["upload_url"],
            data=upload_info["upload_fields"],
            files={
                "file": (
                    "payload.json",
                    payload_json.encode("utf-8"),
                    "application/json",
                )
            },
            timeout=self.timeout,
        )
        self._raise_for_status(post_response)

        parent_request_id = upload_info["parent_request_id"]
        print(
            f"Payload uploaded. parent_request_id: {parent_request_id} "
            f"(poll GET /requests/{parent_request_id} for status)"
        )
        return parent_request_id

    def upload_payload(
        self,
        job_name: str,
        protein: "ProteinInput",
        ligands: "List[LigandInput]",
        cofactors_ions: "Optional[List[LigandInput]]" = None,
        local_filepath: Optional[str] = None,
    ) -> str:
        """
        Convenience method: request a presigned URL and upload the payload in one call.

        Combines request_payload_upload() and upload_payload_file(). Use the separate
        methods directly if you need to inspect or store the upload_info between steps.

        Args:
            job_name:        Job name for the prediction run.
            protein:         ProteinInput (name, pdb_block, optional msa_filenames).
            ligands:         List of LigandInput.
            cofactors_ions:  Optional list of cofactor/ion LigandInput.
            local_filepath:  Optional path to save the payload JSON locally before uploading.

        Returns:
            parent_request_id – use with GET /requests/{parent_request_id} to poll status.
        """
        upload_info = self.request_payload_upload(job_name)
        return self.upload_payload_file(
            upload_info=upload_info,
            protein=protein,
            ligands=ligands,
            cofactors_ions=cofactors_ions,
            local_filepath=local_filepath,
        )

    def clean_protein(self, pdb_block: str) -> str:
        """
        Clean and standardise a protein PDB block.

        Calls POST /clean which normalises atom/residue names, converts non-standard
        amino acids, resolves alternate locations, and renumbers atoms.

        Args:
            pdb_block: Raw PDB file content.

        Returns:
            Cleaned PDB block as a string.

        Example:
            raw_pdb = load_pdb_file("./data/protein_ACSL.pdb")
            clean_pdb = client.clean_protein(raw_pdb)
            protein = ProteinInput(name="ACSL", pdb_block=clean_pdb)
        """
        response = self.session.post(
            f"{self.base_url}/clean",
            json={"pdb_block": pdb_block},
            timeout=self.timeout,
        )
        self._raise_for_status(response)
        return response.json()["pdb_block"]

    def create_request(
        self,
        job_name: str,
        protein: ProteinInput,
        ligands: List[LigandInput],
        cofactors_ions: Optional[List[LigandInput]] = None,
    ) -> Dict:
        """
        Create a new async prediction request for one protein with multiple ligands.

        Args:
            job_name: Unique identifier for this job.
            protein: ProteinInput with name, pdb_block, and optional msa_filenames.
                     msa_filenames contains one MSA filename per protein chain (or None to skip a chain).
                     Leave msa_filenames empty to run without MSA.
            ligands: List of ligands to predict with this protein.
            cofactors_ions: Optional list of cofactors/ions. Same format as ligands: name + molblock.

        Returns:
            Dict with parent_request_id, status, created_at, total_ligands, message.

        Example (with MSA):
            msa_filename = client.upload_msa("./data/chain_A.csv")
            protein = ProteinInput(
                name="target_protein",
                pdb_block="ATOM ...",
                msa_filenames=[msa_filename],  # one filename per chain
            )
            ligands = [LigandInput(name="lig_1", molblock="...")]
            response = client.create_request(
                job_name="run_with_msa",
                protein=protein,
                ligands=ligands,
            )
        """
        if cofactors_ions is None:
            cofactors_ions = []

        payload = {
            "job_name": job_name,
            "protein": {
                "name": protein.name,
                "pdb_block": protein.pdb_block,
                "msa_filenames": protein.msa_filenames,
            },
            "ligands": [
                {"name": ligand.name, "molblock": ligand.molblock} for ligand in ligands
            ],
            "cofactors_ions": [
                {"name": c.name, "molblock": c.molblock} for c in cofactors_ions
            ],
        }

        response = self.session.post(
            f"{self.base_url}/requests",
            json=payload,
            timeout=self.timeout,
        )
        self._raise_for_status(response)

        # Check for rate limit headers
        if "x-rate-limit-remaining" in response.headers:
            print(
                f"[Quota] Remaining: {response.headers['x-rate-limit-remaining']}/{response.headers.get('x-rate-limit-limit', 'N/A')}"
            )

        return response.json()

    def get_request_status(self, parent_request_id: str) -> AsyncRequest:
        """
        Get the status of a request and all its ligand predictions

        Args:
            parent_request_id: The parent request ID returned from create_request

        Returns:
            AsyncRequest object with all ligand statuses and summary

        Example:
            request = client.get_request_status("abc-123-def")
            print(f"Status: {request.status}")
            print(f"Progress: {request.status_summary.completed_percent}%")

            for ligand in request.ligands:
                print(f"  {ligand.ligand_name}: {ligand.status}")
        """
        response = self.session.get(
            f"{self.base_url}/requests/{parent_request_id}",
            timeout=self.timeout,
        )
        self._raise_for_status(response)
        data = response.json()

        # Parse ligand statuses
        ligands = [
            LigandStatus(
                job_name=lig.get("job_name", ""),
                request_id=lig["request_id"],
                status=lig["status"],
                protein_name=lig.get("protein_name", ""),
                ligand_name=lig["ligand_name"],
                created_at=lig["created_at"],
                updated_at=lig["updated_at"],
                progress=lig.get("progress"),
                result=lig.get("result"),
                error=lig.get("error"),
            )
            for lig in data["ligands"]
        ]

        # Parse status summary
        summary_data = data["status_summary"]
        status_summary = StatusSummary(
            total=summary_data["total"],
            pending_upload=summary_data.get("pending_upload", 0),
            pending=summary_data.get("pending", 0),
            starting=summary_data.get("starting", 0),
            processing=summary_data.get("processing", 0),
            completed=summary_data.get("completed", 0),
            failed=summary_data.get("failed", 0),
            pending_upload_percent=summary_data.get("pending_upload_percent", 0.0),
            pending_percent=summary_data.get("pending_percent", 0.0),
            starting_percent=summary_data.get("starting_percent", 0.0),
            processing_percent=summary_data.get("processing_percent", 0.0),
            completed_percent=summary_data.get("completed_percent", 0.0),
            failed_percent=summary_data.get("failed_percent", 0.0),
        )

        raw_status = data["status"]
        try:
            parsed_status = RequestStatus(raw_status)
        except ValueError:
            parsed_status = RequestStatus.PENDING  # treat unknown statuses as PENDING

        return AsyncRequest(
            parent_request_id=data["parent_request_id"],
            status=parsed_status,
            created_at=data["created_at"],
            updated_at=data["updated_at"],
            total_ligands=data["total_ligands"],
            ligands=ligands,
            status_summary=status_summary,
        )

    def wait_for_completion(
        self,
        parent_request_id: str,
        check_interval: int = 10,
        max_wait_time: Optional[int] = None,
        progress_callback: Optional[Callable[[AsyncRequest], None]] = None,
    ) -> AsyncRequest:
        """
        Wait for a request to complete (all ligands finished)

        Args:
            parent_request_id: The parent request ID
            check_interval: Time between status checks in seconds (default: 10)
            max_wait_time: Maximum time to wait in seconds (None = wait indefinitely)
            progress_callback: Optional callback function called on each status check

        Returns:
            Final AsyncRequest object

        Raises:
            TimeoutError: If max_wait_time is exceeded
            Exception: If the request fails

        Example:
            def show_progress(request):
                print(f"Progress: {request.status_summary.completed_percent}% complete")

            result = client.wait_for_completion(
                parent_request_id,
                check_interval=5,
                max_wait_time=3600,
                progress_callback=show_progress
            )
        """
        start_time = time.time()

        while True:
            # Check status
            request = self.get_request_status(parent_request_id)

            # Call progress callback if provided
            if progress_callback:
                progress_callback(request)

            # Check if completed or failed
            if request.status in [RequestStatus.COMPLETED, RequestStatus.FAILED]:
                return request

            # Check timeout
            if max_wait_time and (time.time() - start_time) > max_wait_time:
                raise TimeoutError(
                    f"Request {parent_request_id} did not complete within {max_wait_time} seconds"
                )

            # Wait before next check
            time.sleep(check_interval)

    def get_results(self, parent_request_id: str) -> Dict[str, Any]:
        """
        Get all results for completed ligand predictions

        Args:
            parent_request_id: The parent request ID

        Returns:
            Dict mapping ligand names to their results

        Example:
            results = client.get_results("abc-123-def")
            for ligand_name, result in results.items():
                if result["status"] == "COMPLETED":
                    print(f"{ligand_name}: affinity = {result['data'].get('affinity')}")
                else:
                    print(f"{ligand_name}: {result['error']}")
        """
        request = self.get_request_status(parent_request_id)

        results = {}
        for ligand in request.ligands:
            if ligand.status == "COMPLETED":
                results[ligand.ligand_name] = {
                    "status": "COMPLETED",
                    "data": ligand.result,
                    "request_id": ligand.request_id,
                }
            elif ligand.status == "FAILED":
                results[ligand.ligand_name] = {
                    "status": "FAILED",
                    "error": ligand.error,
                    "request_id": ligand.request_id,
                }
            else:
                results[ligand.ligand_name] = {
                    "status": ligand.status,
                    "request_id": ligand.request_id,
                }

        return results


# Helper functions for loading structures from files
def load_pdb_file(filepath: str) -> str:
    """Load PDB file content"""
    with open(filepath, "r") as f:
        return f.read()


def load_molblock_file(filepath: str) -> str:
    """Load molblock/SDF file content"""
    with open(filepath, "r") as f:
        return f.read()


def load_msa_file(filepath: str) -> str:
    """
    Load an MSA file in CSV format.

    The file should be a CSV where each row represents an aligned sequence.
    One MSA file corresponds to one protein chain.
    """
    with open(filepath, "r") as f:
        return f.read()