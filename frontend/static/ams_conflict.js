// Polls /api/ams/conflict/open and shows a simple confirm/cancel dialog
(function(){
    let current = null;

    async function fetchConflicts(){
        try{
                // Guard: do nothing if frontend state indicates no AMS
                if (document.body && document.body.classList.contains('no-ams')) return;
                const res = await fetch('/api/ams/conflict/open');
            if(!res.ok) return;
            const data = await res.json();
            if(data && data.length>0){
                if(!current || current.id !== data[0].id){
                    current = data[0];
                    showModal(current);
                }
            }
        }catch(e){
            console.error('Failed to fetch AMS conflicts', e);
        }
    }

    function showModal(conflict){
            if (document.body && document.body.classList.contains('no-ams')) return;
        const modal = document.getElementById('amsConflictModal');
        if(!modal) return;
        document.getElementById('ams-conflict-title').textContent = `AMS Slot ${conflict.slot} – Spule ersetzen?`;
        document.getElementById('ams-conflict-text').textContent = 'Im AMS wurde eine neue Spule mit RFID erkannt. Der Slot ist aktuell manuell belegt.';
        // attach handlers (store current in closure)
        modal.style.display = 'block';
        // ensure buttons are enabled
        const confirmBtn = document.getElementById('ams-conflict-confirm-btn');
        const cancelBtn = document.getElementById('ams-conflict-cancel-btn');
        confirmBtn.disabled = false;
        cancelBtn.disabled = false;
    }

    window.onAmsConflictConfirm = async function(){
        if(!current) return;
            if (document.body && document.body.classList.contains('no-ams')) return;
        try{
            await fetch('/api/ams/conflict/confirm', {
                method: 'POST',
                headers: {'Content-Type':'application/json'},
                body: JSON.stringify({
                    ams_id: current.ams_id,
                    slot: current.slot,
                    manual_spool_id: current.manual_spool_id,
                    rfid_spool_id: current.rfid_spool_id || null
                })
            });
        }catch(e){console.error(e)}
        closeAmsConflictModal();
        window.location.reload();
    };

    window.onAmsConflictCancel = async function(){
        if(!current) return;
            if (document.body && document.body.classList.contains('no-ams')) return;
        try{
            await fetch('/api/ams/conflict/cancel', {
                method: 'POST',
                headers: {'Content-Type':'application/json'},
                body: JSON.stringify({ams_id: current.ams_id, slot: current.slot})
            });
        }catch(e){console.error(e)}
        closeAmsConflictModal();
        window.location.reload();
    };

    window.closeAmsConflictModal = function(){
        const modal = document.getElementById('amsConflictModal');
        if(modal) modal.style.display = 'none';
        current = null;
    };

    // Poll every 5s
    setInterval(fetchConflicts, 5000);
    window.addEventListener('load', fetchConflicts);
})();
