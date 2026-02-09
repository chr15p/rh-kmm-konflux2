import urllib.parse
from typing import Any, Dict, List, Optional
import requests

class Konflux:
    def __init__(self, url, token, namespace, api, kind, verify):
        self.url = f"{url.rstrip('/')}/apis/{api}/namespaces/{namespace}/{kind}"
        self.kind = kind
        self.headers = self.build_headers(token)
        self.verify = verify
        self.namespace = namespace
        self.timeout = 30


    def build_headers(self, token: Optional[str]) -> Dict[str, str]:
        headers = {"Accept": "application/json"}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        return headers


    def get(self, name: str=None, label_selector: dict=None) -> Dict[str, Any]:
        """
        Fetch pods in the given namespace. If the API enforces pagination, follow continue tokens.
        """
        # Some clusters may paginate; handle 'continue'
        all_items: List[Dict[str, Any]] = []


        params: Dict[str, str] = {}
        if name and label_selector:
            raise SystemExit("only one of name and label_selector can be specified")
        if name:
            url = f"{self.url}/{name}"
        elif label_selector:
            querystring=""
            for k,v in label_selector.items():
                querystring += f",{k}={v}"
            url = f"{self.url}?labelSelector={urllib.parse.quote(querystring[1:].encode())}"
        else:
            url = self.url

        session = requests.Session()

        while True:
            resp = session.get(url, headers=self.headers, params=params, verify=self.verify, timeout=self.timeout)
            if resp.status_code == 401:
                raise SystemExit("Unauthorized (401). Provide a valid token via --token.")
            if resp.status_code == 403:
                raise SystemExit(f"Forbidden (403). Token lacks permission to list {self.kind} in namespace '{self.namespace}'.")
            resp.raise_for_status()
            body = resp.json()
            items = body.get("items", None)
            if items:
                all_items.extend(items)
            else:
                all_items.append(body)
            cont = body.get("metadata", {}).get("continue")
            if cont:
                params["continue"] = cont
            else:
                break

        #return {"items": all_items}
        return all_items


    def create(self, manifest: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create a pod in the given namespace. Returns the created/existing pod object.
        Treat HTTP 409 (AlreadyExists) as success and return the existing object by GET.
        """
        resp = requests.post(self.url, headers={**self.headers, "Content-Type": "application/json"}, json=manifest, verify=self.verify, timeout=self.timeout)
        if resp.status_code == 201:
            return resp.json()
        if resp.status_code == 409:
            # Already exists - fetch and return
            obj_name = manifest.get("metadata", {}).get("name", "")
            if not obj_name:
                return resp.json()

            existing_object = self.get(name = obj_name)
            return existing_object
        # Other errors
        resp.raise_for_status()
        return resp.json()


