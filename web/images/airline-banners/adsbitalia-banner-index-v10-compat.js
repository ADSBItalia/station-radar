/**
 * Compatibility adapter for ADSBItalia banner-engine-v10.
 *
 * The current operator index contains both legacy string values and newer
 * structured records. Engine v10 expects every value to be an image filename.
 */
(function () {
    "use strict";

    const nativeFetch = window.fetch.bind(window);

    function clean(value) {
        return String(value || "").trim();
    }

    function filename(record) {
        if (typeof record === "string") return clean(record);
        if (!record || typeof record !== "object") return "";

        const storedFilename = clean(record.filename);
        if (storedFilename) return storedFilename;

        const bannerCode = clean(record.banner_icao).toUpperCase();
        if (bannerCode === "IEI") return "aviazione-dell-esercito-italiano.png";
        if (bannerCode === "MMI") return "marina-militare.png";
        if (bannerCode === "IAM") return "aeronautica-militare.png";
        if (bannerCode === "CFC") return "royal-canadian-air-force.png";
        if (bannerCode === "RCH") return "united-states-air-force.png";
        if (bannerCode === "RRR") return "royal-air-force.png";

        const opRaw = clean(record.operator || record.category).toUpperCase();
        const isGovOrEmergency = /AMBULANCE|AMBULANZA|POLICE|POLIZIA|POLIZEI|MILITARY|MILITARE|ARMY|NAVY|AIR FORCE|AERONAUTICA|ESERCITO|MARINA|RESCUE|DOCTOR|MEDIC|EVAC|COAST GUARD|COSTIERA|VIGILI|FIRE|FEUERWEHR/.test(opRaw);
        if (bannerCode && !isGovOrEmergency) return bannerCode + ".png";

        const op = clean(record.operator).toUpperCase();
        if (!op) return "";

        // Specific foreign air forces / military operators:
        if (op.includes("ROYAL CANADIAN AIR FORCE") || op.includes("CANADIAN ARMED FORCES")) return "royal-canadian-air-force.png";
        if (op.includes("UNITED STATES AIR FORCE") || op.includes("U.S. AIR FORCE") || op.includes("US AIR FORCE")) return "united-states-air-force.png";
        if (op.includes("UNITED STATES ARMY") || op.includes("U.S. ARMY") || op.includes("US ARMY")) return "united-states-army.png";
        if (op.includes("UNITED STATES NAVY") || op.includes("U.S. NAVY") || op.includes("US NAVY")) return "united-states-navy.png";
        if (op.includes("ROYAL AUSTRALIAN AIR FORCE")) return "royal-australian-air-force.png";
        if (op.includes("ROYAL AIR FORCE") && !op.includes("CANADIAN") && !op.includes("AUSTRALIAN")) return "royal-air-force.png";
        if (op.includes("FRENCH AIR FORCE") || op.includes("ARMEE DE L'AIR")) return "french-air-force.png";
        if (op.includes("ISRAELI AIR FORCE")) return "israeli-air-force.png";

        // Italian Institutional & Military:
        if (op.includes("ESERCITO ITALIANO") || op.includes("ITALIAN ARMY") || op.includes("AVIAZIONE DELL'ESERCITO")) return "aviazione-dell-esercito-italiano.png";
        if (op.includes("MARINA MILITARE") || op.includes("ITALIAN NAVY")) return "marina-militare.png";
        if (op.includes("AERONAUTICA MILITARE") || op.includes("ITALIAN AIR FORCE")) return "aeronautica-militare.png";
        if (op.includes("GUARDIA DI FINANZA") || op.includes("FINANZA") || op.includes("GDF")) return "guardia-di-finanza.png";
        if (op.includes("CARABINIERI")) return "carabinieri.png";
        if (op.includes("GUARDIA COSTIERA") || op.includes("COSTIERA")) return "guardia-costiera.png";
        if (op.includes("POLIZIA DI STATO")) return "polizia-di-stato.png";
        if (op.includes("VIGILI DEL FUOCO")) return "vigili-del-fuoco.png";

        return "";
    }

    function normalizeSection(section) {
        const output = {};
        if (!section || typeof section !== "object") return output;

        for (const [key, record] of Object.entries(section)) {
            const value = filename(record);
            if (value) output[key] = value;
        }
        return output;
    }

    window.fetch = async function (input, init) {
        const response = await nativeFetch(input, init);
        const url = typeof input === "string" ? input : clean(input && input.url);

        if (!url.includes("operator-banner-index.json")) return response;

        try {
            const data = await response.clone().json();
            data.by_hex = normalizeSection(data.by_hex);
            data.by_registration = normalizeSection(data.by_registration);

            const headers = new Headers(response.headers);
            headers.delete("content-length");
            headers.delete("content-encoding");

            return new Response(JSON.stringify(data), {
                status: response.status,
                statusText: response.statusText,
                headers
            });
        } catch (_) {
            return response;
        }
    };
})();
