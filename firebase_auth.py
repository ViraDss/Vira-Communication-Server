"""
Firebase Client Authentication
Verifies that a connecting client's ID exists in the Firebase Realtime Database
under the following structure:

  clients/
    app_clients/   { client_id: uid, ... }
    drone_clients/ { client_id: name, ... }
"""

import logging
from typing import Optional, Tuple

logger = logging.getLogger(__name__)

# This will be set by main.py after Firebase initialisation
_firebase_db = None


def init_firebase_auth(db):
    """Call this once from main.py after pyrebase.initialize_app()."""
    global _firebase_db
    _firebase_db = db
    logger.info("Firebase auth module initialised with Realtime Database reference.")


def verify_client_id(client_id: str, expected_type: Optional[str] = None) -> Tuple[bool, str]:
    """
    Synchronously check whether *client_id* exists in the Firebase Realtime DB.

    The DB is expected to have this shape:
        clients/
            app_clients/   { "<client_id>": "<uid>" }
            drone_clients/ { "<client_id>": "<drone_name>" }

    Parameters
    ----------
    client_id     : the ID sent by the connecting client (path segment)
    expected_type : "application" | "drone" | None
                    When given, only the matching sub-tree is searched.
                    When None, both sub-trees are searched.

    Returns
    -------
    (True,  "app_client"|"drone_client") on success
    (False, reason_string)               on failure
    """
    if _firebase_db is None:
        logger.error("Firebase DB not initialised – allowing connection by default.")
        # Fail-open: if Firebase is not ready, don't block legitimate clients.
        return True, "firebase_unavailable"

    try:
        check_app    = expected_type in (None, "application")
        check_drone  = expected_type in (None, "drone")

        if check_app:
            snapshot = _firebase_db.child("clients").child("app_clients").child(client_id).get()
            value = snapshot.val()
            if value is not None:
                logger.info(f"Client '{client_id}' verified as app_client (uid={value})")
                return True, "app_client"

        if check_drone:
            snapshot = _firebase_db.child("clients").child("drone_clients").child(client_id).get()
            value = snapshot.val()
            if value is not None:
                logger.info(f"Client '{client_id}' verified as drone_client (name={value})")
                return True, "drone_client"

        logger.warning(f"Client '{client_id}' NOT found in Firebase clients registry.")
        return False, "client_not_found"

    except Exception as exc:
        logger.error(f"Firebase lookup failed for client '{client_id}': {exc}")
        # Fail-open on network / permission errors so a Firebase outage doesn't
        # take down the whole server.
        return True, "firebase_error"
