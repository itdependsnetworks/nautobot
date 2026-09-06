/**
 * Live list of software image files matching the selected software version and device type.
 *
 * Attached to any create/edit form containing a `[data-nb-software-image-picker]` container (rendered by
 * `dcim/inc/software_image_list.html`, placed in a form layout via `SoftwareImagePanel`). Configuration comes from
 * the container's data attributes so the same script serves every form that includes the panel.
 */
(function () {
    "use strict";

    const ERROR_MESSAGE = "Error retrieving software image list";

    /** The label of the selected option, as the user sees it. Select2 keeps the underlying `select` in step. */
    function selectedLabel(select) {
        return select?.selectedOptions[0]?.text ?? "";
    }

    /** A `b` element, so a version or device type name stands out mid-sentence and does not wrap. */
    function emphasized(text) {
        const element = document.createElement("b");
        element.className = "text-nowrap";
        element.textContent = text;
        return element;
    }

    async function fetchImages(url, params) {
        const response = await fetch(`${url}?${new URLSearchParams(params)}`, {
            headers: { Accept: "application/json" },
        });
        if (!response.ok) {
            throw new Error(`${response.status} ${response.statusText}`);
        }
        return response.json();
    }

    function initializePicker(container) {
        const form = container.closest("form");
        if (!form || container.dataset.nbSoftwareImagePickerBound === "true") {
            return;
        }
        container.dataset.nbSoftwareImagePickerBound = "true";

        const description = container.querySelector("[data-nb-software-image-description]");
        const list = container.querySelector("[data-nb-software-image-list]");
        const imageUrl = container.dataset.nbSoftwareImageUrl;
        const loaderSrc = container.dataset.nbLoaderSrc;
        const autoId = container.dataset.nbFormAutoId || "id_%s";
        const versionFieldName = container.dataset.nbVersionField || "software_version";
        // Empty when the form has no device type field (virtual machines, inventory items): images are then
        // listed for the software version alone.
        const deviceTypeFieldName = container.dataset.nbDeviceTypeField || "";

        const field = (name) => form.querySelector(`select${window.nb.form.getFieldAutoId(autoId, name)}`);
        const version = field(versionFieldName);
        const deviceType = deviceTypeFieldName ? field(deviceTypeFieldName) : null;
        if (!version) {
            return;
        }

        const show = () => {
            container.classList.remove("d-none");
            container.classList.add("d-flex");
        };

        const hide = () => {
            container.classList.remove("d-flex");
            container.classList.add("d-none");
            description.textContent = "";
            list.textContent = "";
        };

        const describe = (...nodes) => {
            description.textContent = "";
            description.append(...nodes);
        };

        const listImages = (images) => {
            list.replaceChildren(
                ...images.map((image) => {
                    const item = document.createElement("li");
                    const link = document.createElement("a");
                    link.href = image.url.replace("api/", "");
                    link.textContent = image.image_file_name;
                    item.appendChild(link);
                    return item;
                }),
            );
        };

        const describeForVersion = async (versionId) => {
            const data = await fetchImages(imageUrl, { software_version: versionId });
            const versionLabel = emphasized(selectedLabel(version));
            if (data.count === 0) {
                describe("No software images found for software version ", versionLabel);
            } else {
                describe("Software version ", versionLabel, " provides the following software images:");
                listImages(data.results);
            }
        };

        const describeForDeviceType = async (versionId, deviceTypeId) => {
            const [deviceTypeImages, defaultImage] = await Promise.all([
                fetchImages(imageUrl, { software_version: versionId, device_types: deviceTypeId }),
                fetchImages(imageUrl, { software_version: versionId, default_image: "true" }),
            ]);
            const deviceTypeLabel = emphasized(selectedLabel(deviceType));
            const versionLabel = emphasized(selectedLabel(version));
            if (defaultImage.count === 0 && deviceTypeImages.count === 0) {
                describe("No software images found for device type ", deviceTypeLabel);
            } else if (deviceTypeImages.count === 0) {
                describe(
                    "Software version ",
                    versionLabel,
                    " provides no software images for device type ",
                    deviceTypeLabel,
                    ". The default image is:",
                );
                listImages(defaultImage.results.slice(0, 1));
            } else {
                describe(
                    "Software version ",
                    versionLabel,
                    " provides the following software images for device type ",
                    deviceTypeLabel,
                    ":",
                );
                listImages(deviceTypeImages.results);
            }
        };

        const populate = async (versionId) => {
            list.textContent = "";
            description.textContent = "";
            if (loaderSrc) {
                const loader = document.createElement("img");
                loader.alt = "Loading software images";
                loader.src = loaderSrc;
                description.appendChild(loader);
            }
            list.classList.add("invisible"); // prevent flicker while the new list is fetched
            show();

            const deviceTypeId = deviceType?.selectedOptions[0]?.value;
            if (deviceType && !deviceTypeId) {
                describe(emphasized("Unable to display software image list. Select a device type first."));
                return;
            }
            try {
                if (deviceType) {
                    await describeForDeviceType(versionId, deviceTypeId);
                } else {
                    await describeForVersion(versionId);
                }
            } catch {
                describe(emphasized(ERROR_MESSAGE));
            } finally {
                list.classList.remove("invisible");
            }
        };

        version.addEventListener("change", () => (version.value ? populate(version.value) : hide()));
        if (version.value) {
            populate(version.value);
        }
    }

    function initialize(scope) {
        const root = scope && scope.querySelectorAll ? scope : document;
        root.querySelectorAll("[data-nb-software-image-picker]").forEach((container) => {
            const form = container.closest("form");
            const type = form?.getAttribute("data-nb-obj-type");
            if (!type) {
                return;
            }
            // Select2 must be attached to the version select before the picker reads it. On a full page load
            // `nb-form:load:<type>` announces that (see ui/src/js/form.js); in the embedded-create modal this script
            // arrives with the swapped content and may run after that event has already fired, so initialize at once
            // when Select2 is already there.
            if (form.querySelector("select.select2-hidden-accessible[name$='software_version']")) {
                initializePicker(container);
                return;
            }
            form.addEventListener(`nb-form:load:${type}`, () => initializePicker(container), { once: true });
        });
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", () => initialize(document));
    } else {
        initialize(document);
    }
    if (window.htmx) {
        window.htmx.onLoad((content) => initialize(content));
    }

    window.nb = window.nb || {};
    window.nb.softwareImagePicker = { initialize: initialize };
})();
