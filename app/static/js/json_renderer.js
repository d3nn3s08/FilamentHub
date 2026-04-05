(function(){
    function copyToClipboard(text){
        try {
            if (navigator && navigator.clipboard && navigator.clipboard.writeText){
                return navigator.clipboard.writeText(String(text));
            }
        } catch(_) {
            // ignore
        }
    }

    function renderJsonTree(obj, container){
        if (!container) return;
        container.innerHTML = '';
        const root = buildJsonNode('(root)', obj, true);
        container.appendChild(root);
    }

    function buildJsonNode(key, value, expanded){
        const node = document.createElement('div');
        node.className = 'json-node';

        const row = document.createElement('div');
        row.className = 'json-row';

        const toggle = document.createElement('span');
        toggle.className = 'json-toggle';

        const keyEl = document.createElement('span');
        keyEl.className = 'json-key';
        keyEl.textContent = key;

        const typeEl = document.createElement('span');
        typeEl.className = 'json-type';

        const copyBtn = document.createElement('button');
        copyBtn.className = 'copy-btn';

        const children = document.createElement('div');
        children.className = 'json-children';

        if (value !== null && typeof value === 'object'){
            const isArray = Array.isArray(value);
            typeEl.textContent = isArray ? `[${value.length}]` : '{ }';
            copyBtn.textContent = 'Copy';
            copyBtn.addEventListener('click', () => copyToClipboard(JSON.stringify(value, null, 2)));

            toggle.textContent = expanded ? '-' : '+';
            toggle.addEventListener('click', () => {
                const currentlyHidden = children.style.display === 'none';
                children.style.display = currentlyHidden ? 'block' : 'none';
                toggle.textContent = currentlyHidden ? '-' : '+';
            });

            row.appendChild(toggle);
            row.appendChild(keyEl);
            row.appendChild(typeEl);
            row.appendChild(copyBtn);
            node.appendChild(row);
            node.appendChild(children);

            for (const k of Object.keys(value)){
                children.appendChild(buildJsonNode(k, value[k], false));
            }
            children.style.display = expanded ? 'block' : 'none';
        } else {
            const val = document.createElement('span');
            val.className = 'json-value';
            val.textContent = String(value);

            copyBtn.textContent = 'Copy';
            copyBtn.addEventListener('click', () => copyToClipboard(String(value)));

            row.appendChild(toggle);
            row.appendChild(keyEl);
            row.appendChild(document.createTextNode(':'));
            row.appendChild(val);
            row.appendChild(copyBtn);
            node.appendChild(row);
        }
        return node;
    }

    if (typeof window !== 'undefined'){
        window.renderJsonTree = renderJsonTree;
    }
})();
