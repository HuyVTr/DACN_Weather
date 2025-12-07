async function loadFileList() {
    const res = await fetch("/list");
    const data = await res.json();

    const select = document.getElementById("fileList");
    data.files.forEach(f => {
        const opt = document.createElement("option");
        opt.textContent = f;
        opt.value = f;
        select.appendChild(opt);
    });
}

async function loadFile() {
    const name = document.getElementById("fileList").value;
    const res = await fetch(`/read?name=${name}`);
    const data = await res.json();

    let html = `
        <h3 style="margin-bottom:15px;">Data from: 
            <span style="color:#3a8bff">${data.file}</span>
        </h3>
        <table><tr>
    `;

    // Header
    Object.keys(data.rows[0]).forEach(col => {
        html += `<th>${col.toUpperCase()}</th>`;
    });
    html += "</tr>";

    // Rows
    data.rows.forEach(row => {
        html += "<tr>";
        Object.values(row).forEach(v => {
            html += `<td>${v}</td>`;
        });
        html += "</tr>";
    });

    html += "</table>";
    document.getElementById("output").innerHTML = html;
}

loadFileList();
