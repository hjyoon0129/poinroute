(function () {
    /*
     * 포인루트 지역 데이터
     * 메인 검색/등록폼에서는 동/읍/면을 사용하지 않고,
     * 시/도 + 군/구까지만 사용한다.
     */
    const AREA_DATA = {
        "서울": [
            "강남구", "서초구", "송파구", "마포구", "종로구", "용산구", "성동구", "광진구",
            "동대문구", "중랑구", "성북구", "강북구", "도봉구", "노원구", "은평구",
            "서대문구", "양천구", "강서구", "구로구", "금천구", "영등포구", "동작구",
            "관악구", "강동구"
        ],
        "인천": [
            "남동구", "서구", "연수구", "중구", "미추홀구", "부평구", "계양구"
        ],
        "경기": [
            "수원시", "성남시", "용인시", "고양시", "부천시", "안산시", "안양시",
            "남양주시", "화성시", "평택시", "의정부시"
        ],
        "부산": [
            "해운대구", "수영구", "기장군", "중구", "서구", "동구", "영도구",
            "부산진구", "동래구", "남구", "북구", "강서구", "사하구", "금정구",
            "연제구", "사상구"
        ],
        "대구": [
            "중구", "수성구", "달서구", "동구"
        ],
        "광주": [
            "북구", "광산구", "서구"
        ],
        "대전": [
            "유성구", "서구", "중구"
        ],
        "울산": [
            "남구", "중구", "울주군"
        ],
        "세종": [
            "세종시"
        ],
        "강원": [
            "강릉시", "춘천시", "속초시"
        ],
        "충북": [
            "청주시", "충주시", "제천시"
        ],
        "충남": [
            "천안시", "아산시", "당진시"
        ],
        "전북": [
            "전주시", "군산시", "익산시"
        ],
        "전남": [
            "여수시", "순천시", "목포시"
        ],
        "경북": [
            "포항시", "구미시", "경주시"
        ],
        "경남": [
            "창원시", "김해시", "거제시"
        ],
        "제주": [
            "제주시", "서귀포시"
        ]
    };

    let ps = null;
    let map = null;
    let marker = null;
    let isMapInitialized = false;

    document.addEventListener('DOMContentLoaded', function () {
        initNavbarShadow();
        initDatePicker();
        initFormRegionSelectors();
        initListRegionSelectors();
        initPrettySelects();
        initCourseForm();
        initMapModal();
    });

    function qs(selector, scope = document) {
        return scope.querySelector(selector);
    }

    function qsa(selector, scope = document) {
        return Array.from(scope.querySelectorAll(selector));
    }

    function initNavbarShadow() {
        const navbar = qs('.top-navbar');
        if (!navbar) return;

        window.addEventListener('scroll', function () {
            navbar.style.boxShadow = window.scrollY > 10
                ? '0 8px 28px rgba(20, 36, 80, 0.08)'
                : '0 4px 18px rgba(0, 0, 0, 0.025)';
        });
    }

    /*
     * 고급 캘린더
     * - 무조건 input 아래로 표시
     * - 바깥 « » = 연도 이동
     * - 안쪽 ‹ › = 월 이동
     * - 가운데는 "2026년 5월" 텍스트만 표시
     * - 년/월 드롭다운 제거
     */
    function initDatePicker() {
        if (typeof flatpickr === 'undefined') return;

        flatpickr('.date-picker', {
            locale: 'ko',
            dateFormat: 'Y-m-d',
            disableMobile: true,
            allowInput: false,
            animate: true,
            monthSelectorType: 'static',
            position: 'below left',

            prevArrow: '',
            nextArrow: '',

            onReady: function (selectedDates, dateStr, instance) {
                enhancePoinrouteCalendar(instance);
            },

            onOpen: function (selectedDates, dateStr, instance) {
                enhancePoinrouteCalendar(instance);
                forceCalendarBelow(instance);
            },

            onMonthChange: function (selectedDates, dateStr, instance) {
                updatePoinrouteCalendarHeader(instance);
                forceCalendarBelow(instance);
            },

            onYearChange: function (selectedDates, dateStr, instance) {
                updatePoinrouteCalendarHeader(instance);
                forceCalendarBelow(instance);
            },

            onValueUpdate: function (selectedDates, dateStr, instance) {
                updatePoinrouteCalendarHeader(instance);
            }
        });
    }

    function enhancePoinrouteCalendar(instance) {
        if (!instance || !instance.calendarContainer) return;

        const calendar = instance.calendarContainer;
        calendar.classList.add('poinroute-calendar');

        if (!calendar.querySelector('.poinroute-calendar-header')) {
            buildPoinrouteCalendarHeader(instance);
        }

        updatePoinrouteCalendarHeader(instance);
    }

    function buildPoinrouteCalendarHeader(instance) {
        const calendar = instance.calendarContainer;
        const innerContainer = calendar.querySelector('.flatpickr-innerContainer');

        if (!calendar || !innerContainer) return;

        const defaultMonthHeader = calendar.querySelector('.flatpickr-months');

        if (defaultMonthHeader) {
            defaultMonthHeader.setAttribute('aria-hidden', 'true');
        }

        const header = document.createElement('div');
        header.className = 'poinroute-calendar-header';

        const yearPrevBtn = document.createElement('button');
        yearPrevBtn.type = 'button';
        yearPrevBtn.className = 'poinroute-cal-nav year-prev';
        yearPrevBtn.innerHTML = '«';
        yearPrevBtn.title = '이전 연도';

        const monthPrevBtn = document.createElement('button');
        monthPrevBtn.type = 'button';
        monthPrevBtn.className = 'poinroute-cal-nav month-prev';
        monthPrevBtn.innerHTML = '‹';
        monthPrevBtn.title = '이전 월';

        const title = document.createElement('div');
        title.className = 'poinroute-cal-title';
        title.textContent = '';

        const monthNextBtn = document.createElement('button');
        monthNextBtn.type = 'button';
        monthNextBtn.className = 'poinroute-cal-nav month-next';
        monthNextBtn.innerHTML = '›';
        monthNextBtn.title = '다음 월';

        const yearNextBtn = document.createElement('button');
        yearNextBtn.type = 'button';
        yearNextBtn.className = 'poinroute-cal-nav year-next';
        yearNextBtn.innerHTML = '»';
        yearNextBtn.title = '다음 연도';

        header.appendChild(yearPrevBtn);
        header.appendChild(monthPrevBtn);
        header.appendChild(title);
        header.appendChild(monthNextBtn);
        header.appendChild(yearNextBtn);

        calendar.insertBefore(header, innerContainer);

        yearPrevBtn.addEventListener('click', function () {
            instance.changeYear(instance.currentYear - 1);
            instance.redraw();
            updatePoinrouteCalendarHeader(instance);
            forceCalendarBelow(instance);
        });

        yearNextBtn.addEventListener('click', function () {
            instance.changeYear(instance.currentYear + 1);
            instance.redraw();
            updatePoinrouteCalendarHeader(instance);
            forceCalendarBelow(instance);
        });

        monthPrevBtn.addEventListener('click', function () {
            instance.changeMonth(-1);
            updatePoinrouteCalendarHeader(instance);
            forceCalendarBelow(instance);
        });

        monthNextBtn.addEventListener('click', function () {
            instance.changeMonth(1);
            updatePoinrouteCalendarHeader(instance);
            forceCalendarBelow(instance);
        });
    }

    function updatePoinrouteCalendarHeader(instance) {
        if (!instance || !instance.calendarContainer) return;

        const title = instance.calendarContainer.querySelector('.poinroute-cal-title');

        if (!title) return;

        title.textContent = `${instance.currentYear}년 ${instance.currentMonth + 1}월`;
    }

    function forceCalendarBelow(instance) {
        if (!instance || !instance.calendarContainer || !instance.input) return;

        window.requestAnimationFrame(function () {
            const calendar = instance.calendarContainer;
            const inputRect = instance.input.getBoundingClientRect();

            const scrollX = window.scrollX || window.pageXOffset;
            const scrollY = window.scrollY || window.pageYOffset;
            const viewportWidth = window.innerWidth || document.documentElement.clientWidth;
            const safeGap = 14;

            calendar.classList.remove('arrowTop', 'arrowBottom');
            calendar.classList.remove('poinroute-calendar-above');

            calendar.style.position = 'absolute';
            calendar.style.right = 'auto';
            calendar.style.bottom = 'auto';
            calendar.style.transform = 'none';

            const calendarWidth = calendar.offsetWidth || 344;

            let left = inputRect.left + scrollX + (inputRect.width / 2) - (calendarWidth / 2);
            const top = inputRect.bottom + scrollY + 10;

            if (left + calendarWidth > viewportWidth + scrollX - safeGap) {
                left = viewportWidth + scrollX - calendarWidth - safeGap;
            }

            if (left < scrollX + safeGap) {
                left = scrollX + safeGap;
            }

            calendar.style.left = `${Math.round(left)}px`;
            calendar.style.top = `${Math.round(top)}px`;
        });
    }

    function populateSelect(select, values, placeholder) {
        if (!select) return;

        select.innerHTML = '';
        select.appendChild(new Option(placeholder, ''));

        values.forEach(function (value) {
            select.appendChild(new Option(value, value));
        });

        refreshPrettySelect(select);
    }

    /*
     * 루트 등록/수정 폼 지역 셀렉트
     * 동/읍/면 제거 버전.
     */
    function initFormRegionSelectors() {
        const uiReg = qs('#ui_region');
        const uiDist = qs('#ui_district');

        const hiddenReg = qs('#id_start_region');
        const hiddenDist = qs('#id_start_district');

        if (!uiReg || !uiDist || !hiddenReg || !hiddenDist) return;

        populateSelect(uiReg, Object.keys(AREA_DATA), '시/도');

        if (hiddenReg.value) {
            uiReg.value = hiddenReg.value;
            populateSelect(uiDist, AREA_DATA[hiddenReg.value] || [], '군/구');
        } else {
            populateSelect(uiDist, [], '군/구');
        }

        if (hiddenDist.value) {
            uiDist.value = hiddenDist.value;
        }

        refreshPrettySelect(uiReg);
        refreshPrettySelect(uiDist);

        uiReg.addEventListener('change', function () {
            hiddenReg.value = this.value;
            hiddenDist.value = '';

            populateSelect(uiDist, AREA_DATA[this.value] || [], '군/구');
            uiDist.value = '';

            refreshPrettySelect(uiDist);
        });

        uiDist.addEventListener('change', function () {
            hiddenDist.value = this.value;
        });
    }

    /*
     * 리스트 검색 지역 셀렉트
     * 동/읍/면 제거 버전.
     */
    function initListRegionSelectors() {
        const reg = qs('#search_region');
        const dist = qs('#search_district');

        if (!reg || !dist) return;

        const params = new URLSearchParams(window.location.search);
        const savedReg = params.get('start_region') || '';
        const savedDist = params.get('start_district') || '';

        populateSelect(reg, Object.keys(AREA_DATA), '시/도');
        reg.value = savedReg;

        populateSelect(dist, savedReg ? (AREA_DATA[savedReg] || []) : [], '군/구');
        dist.value = savedDist;

        refreshPrettySelect(reg);
        refreshPrettySelect(dist);

        reg.addEventListener('change', function () {
            populateSelect(dist, AREA_DATA[this.value] || [], '군/구');
            dist.value = '';
            refreshPrettySelect(dist);
        });
    }

    function initPrettySelects(scope = document) {
        qsa('select.custom-select', scope).forEach(function (select) {
            if (select.dataset.prettyReady === '1') {
                refreshPrettySelect(select);
                return;
            }

            select.dataset.prettyReady = '1';
            select.classList.add('native-select-hidden');

            const wrapper = document.createElement('div');
            wrapper.className = 'pretty-select';

            const button = document.createElement('button');
            button.type = 'button';
            button.className = 'pretty-select-button';

            const menu = document.createElement('div');
            menu.className = 'pretty-menu';

            wrapper.appendChild(button);
            wrapper.appendChild(menu);
            select.insertAdjacentElement('afterend', wrapper);

            button.addEventListener('click', function (event) {
                event.stopPropagation();

                const isOpen = wrapper.classList.contains('open');

                closeAllPrettySelects();

                if (!isOpen) {
                    wrapper.classList.add('open');
                }
            });

            wrapper.addEventListener('click', function (event) {
                event.stopPropagation();
            });

            refreshPrettySelect(select);
        });

        if (!document.body.dataset.prettyCloseReady) {
            document.body.dataset.prettyCloseReady = '1';
            document.addEventListener('click', closeAllPrettySelects);
        }
    }

    function closeAllPrettySelects() {
        qsa('.pretty-select.open').forEach(function (wrapper) {
            wrapper.classList.remove('open');
        });
    }

    function refreshPrettySelect(select) {
        if (!select) return;

        const wrapper = select.nextElementSibling;
        if (!wrapper || !wrapper.classList.contains('pretty-select')) return;

        const button = qs('.pretty-select-button', wrapper);
        const menu = qs('.pretty-menu', wrapper);
        const selectedOption = select.options[select.selectedIndex] || select.options[0];

        button.textContent = selectedOption ? selectedOption.textContent : '선택';
        button.dataset.empty = select.value ? 'false' : 'true';

        menu.innerHTML = '';

        Array.from(select.options).forEach(function (option) {
            const item = document.createElement('button');
            item.type = 'button';
            item.className = 'pretty-option';
            item.textContent = option.textContent;

            if (option.value === select.value) {
                item.classList.add('selected');
            }

            item.addEventListener('click', function () {
                select.value = option.value;
                select.dispatchEvent(new Event('change', { bubbles: true }));
                select.dispatchEvent(new Event('input', { bubbles: true }));

                refreshPrettySelect(select);
                closeAllPrettySelects();
            });

            menu.appendChild(item);
        });
    }

    function initCourseForm() {
        const form = qs('#courseForm');
        const addBtn = qs('#add-place-btn');
        const container = qs('#place-container');

        if (!form || !addBtn || !container) return;

        updatePlaceNumbers();
        calculateTotals();

        addBtn.addEventListener('click', function () {
            const allCards = qsa('.place-form-card', container);
            const sourceCard = allCards.find(card => !card.classList.contains('is-deleted')) || allCards[0];

            if (!sourceCard) return;

            const newIndex = allCards.length;
            const newCard = sourceCard.cloneNode(true);

            prepareClonedPlaceCard(newCard, newIndex);
            container.appendChild(newCard);

            const totalForms = qs('#id_places-TOTAL_FORMS');

            if (totalForms) {
                totalForms.value = newIndex + 1;
            }

            initPrettySelects(newCard);
            updatePlaceNumbers();
            calculateTotals();
        });

        container.addEventListener('click', function (event) {
            const removeBtn = event.target.closest('.remove-btn');

            if (removeBtn) {
                removePlace(removeBtn);
                return;
            }

            const mapBtn = event.target.closest('.map-open-btn');

            if (mapBtn) {
                openMap(mapBtn);
            }
        });

        form.addEventListener('input', calculateTotals);
        form.addEventListener('change', calculateTotals);
    }

    function prepareClonedPlaceCard(card, index) {
        qsa('.pretty-select', card).forEach(function (wrapper) {
            wrapper.remove();
        });

        qsa('select', card).forEach(function (select) {
            select.classList.remove('native-select-hidden');
            delete select.dataset.prettyReady;
        });

        card.innerHTML = card.innerHTML
            .replace(/places-\d+-/g, `places-${index}-`)
            .replace(/id_places-\d+-/g, `id_places-${index}-`);

        card.classList.remove('is-deleted');
        card.hidden = false;
        card.style.display = '';

        qsa('input, textarea, select', card).forEach(function (field) {
            const name = field.getAttribute('name') || '';

            if (name.endsWith('-DELETE')) {
                field.checked = false;
                return;
            }

            if (field.type === 'checkbox' || field.type === 'radio') {
                field.checked = false;
                return;
            }

            if (field.type === 'file') {
                field.value = '';
                return;
            }

            if (name.endsWith('-id')) {
                field.value = '';
                return;
            }

            if (field.classList.contains('place-day')) {
                field.value = '1';
                return;
            }

            if (field.classList.contains('place-cost')) {
                field.value = '0';
                return;
            }

            field.value = '';
        });

        qsa('.place-image-clear-btn', card).forEach(function (btn) {
            btn.classList.add('is-hidden');
        });

        qsa('.place-image-file-name', card).forEach(function (label) {
            label.textContent = '아직 선택된 이미지가 없습니다.';
        });

        qsa('.place-image-hint', card).forEach(function (hint) {
            hint.textContent = '이 장소 카드에 노출될 이미지입니다.';
        });
    }

    function removePlace(btn) {
        const card = btn.closest('.place-form-card');
        if (!card) return;

        const deleteCheckbox = card.querySelector('input[name$="-DELETE"]');

        if (deleteCheckbox) {
            deleteCheckbox.checked = true;
        }

        card.classList.add('is-deleted');
        card.style.display = 'none';

        updatePlaceNumbers();
        calculateTotals();
    }

    function updatePlaceNumbers() {
        let count = 1;

        qsa('.place-form-card').forEach(function (card) {
            if (card.classList.contains('is-deleted') || card.style.display === 'none') return;

            const title = qs('.place-number', card);

            if (title) {
                title.textContent = `📍 장소 ${count}`;
            }

            count += 1;
        });
    }

    function calculateTotals() {
        let totalCost = 0;

        qsa('.place-form-card').forEach(function (card) {
            if (card.classList.contains('is-deleted') || card.style.display === 'none') return;

            const costInput = qs('.place-cost', card);
            const value = parseInt(costInput?.value || '0', 10);

            if (!Number.isNaN(value)) {
                totalCost += value;
            }
        });

        const displayTotalCost = qs('#display_total_cost');
        const totalCostInput = qs('#id_total_cost');

        if (displayTotalCost) {
            displayTotalCost.textContent = `${totalCost.toLocaleString()}원`;
        }

        if (totalCostInput) {
            totalCostInput.value = totalCost;
        }

        const startInput = qs('#id_travel_start_date');
        const endInput = qs('#id_travel_end_date');
        const displayTotalTime = qs('#display_total_time');
        const totalTimeInput = qs('#id_total_time');

        let dayString = '';

        if (startInput?.value && endInput?.value) {
            const start = new Date(startInput.value);
            const end = new Date(endInput.value);
            const diffTime = end - start;
            const diffDays = Math.ceil(diffTime / (1000 * 60 * 60 * 24));

            if (diffDays === 0) {
                dayString = '당일치기';
            } else if (diffDays > 0) {
                dayString = `${diffDays}박 ${diffDays + 1}일`;
            } else {
                dayString = '날짜 오류';
            }
        }

        if (displayTotalTime) {
            displayTotalTime.textContent = dayString || '입력 대기중';
        }

        if (totalTimeInput) {
            totalTimeInput.value = dayString || '0시간 0분';
        }
    }

    function initMapModal() {
        const closeBtn = qs('#map-close-btn');
        const overlay = qs('#map-overlay');
        const searchBtn = qs('#map-search-btn');
        const keyword = qs('#keyword');

        if (closeBtn) closeBtn.addEventListener('click', closeMap);
        if (overlay) overlay.addEventListener('click', closeMap);
        if (searchBtn) searchBtn.addEventListener('click', searchPlaces);

        document.addEventListener('click', function (event) {
            const startMapBtn = event.target.closest('#start-map-open-btn, .start-map-open-btn, .start-map-btn');

            if (!startMapBtn) return;

            event.preventDefault();
            openMap(startMapBtn);
        });

        if (keyword) {
            keyword.addEventListener('keydown', function (event) {
                if (event.key === 'Enter') {
                    event.preventDefault();
                    searchPlaces();
                }
            });
        }
    }

    function initMap() {
        if (isMapInitialized) return true;

        if (
            typeof kakao === 'undefined' ||
            !kakao.maps ||
            !kakao.maps.services
        ) {
            alert('카카오 지도 API를 불러오지 못했습니다. JavaScript 키, 도메인 등록, libraries=services를 확인해주세요.');
            return false;
        }

        const mapContainer = qs('#map');
        if (!mapContainer) return false;

        const center = new kakao.maps.LatLng(37.566826, 126.9786567);

        map = new kakao.maps.Map(mapContainer, {
            center: center,
            level: 3
        });

        marker = new kakao.maps.Marker({
            position: center
        });

        marker.setMap(map);
        ps = new kakao.maps.services.Places();

        isMapInitialized = true;
        return true;
    }

    function openMap(button) {
        const overlay = qs('#map-overlay');
        const modal = qs('#map-search-container');
        const currentTarget = qs('#current_target_input');
        const currentTargetType = qs('#current_target_type');
        const keyword = qs('#keyword');

        if (!overlay || !modal || !currentTarget || !keyword) return;

        let input = null;
        let targetType = 'place';
        let keywordValue = '';

        const isStartButton =
            button.matches('#start-map-open-btn') ||
            button.classList.contains('start-map-open-btn') ||
            button.classList.contains('start-map-btn');

        if (isStartButton) {
            targetType = 'start';
            input = qs('#start_map_display');

            const region = qs('#ui_region')?.value || '';
            const district = qs('#ui_district')?.value || '';
            const selectedAddress = [region, district].filter(Boolean).join(' ');

            keywordValue = input?.value || selectedAddress;
        } else {
            const card = button.closest('.place-form-card');
            input = card ? qs('.place-name-input', card) : null;
            keywordValue = input?.value || '';
        }

        if (!input) return;

        overlay.hidden = false;
        modal.hidden = false;

        currentTarget.value = input.id || '';

        if (currentTargetType) {
            currentTargetType.value = targetType;
        }

        keyword.value = keywordValue;

        if (initMap()) {
            setTimeout(function () {
                map.relayout();

                if (targetType === 'start' && keywordValue.trim()) {
                    searchPlaces();
                }
            }, 120);
        }
    }

    function closeMap() {
        const overlay = qs('#map-overlay');
        const modal = qs('#map-search-container');

        if (overlay) overlay.hidden = true;
        if (modal) modal.hidden = true;
    }

    function searchPlaces() {
        const keywordInput = qs('#keyword');
        const listEl = qs('#placesList');

        if (!keywordInput || !listEl) return;

        const keyword = keywordInput.value.trim();

        if (!keyword) {
            alert('검색어를 입력해주세요.');
            return;
        }

        if (!initMap() || !ps) {
            alert('지도 서비스 로딩 중입니다. 잠시 후 다시 시도해주세요.');
            return;
        }

        listEl.innerHTML = '<li class="empty-result">검색 중입니다...</li>';

        ps.keywordSearch(keyword, function (data, status) {
            listEl.innerHTML = '';

            if (status === kakao.maps.services.Status.OK) {
                renderPlaces(data);
                return;
            }

            if (status === kakao.maps.services.Status.ZERO_RESULT) {
                listEl.innerHTML = '<li class="empty-result">검색 결과가 없습니다.</li>';
                return;
            }

            listEl.innerHTML = '<li class="empty-result">검색 중 오류가 발생했습니다.</li>';
        });
    }

    function renderPlaces(places) {
        const listEl = qs('#placesList');
        if (!listEl) return;

        const fragment = document.createDocumentFragment();

        places.forEach(function (place) {
            const li = document.createElement('li');

            li.innerHTML = `
                <strong>${escapeHtml(place.place_name)}</strong>
                <span>${escapeHtml(place.address_name || place.road_address_name || '')}</span>
            `;

            li.addEventListener('mouseenter', function () {
                const position = new kakao.maps.LatLng(place.y, place.x);
                map.setCenter(position);
                marker.setPosition(position);
            });

            li.addEventListener('click', function () {
                const targetInputId = qs('#current_target_input')?.value;
                const targetType = qs('#current_target_type')?.value || 'place';
                const targetInput = targetInputId ? document.getElementById(targetInputId) : null;

                if (!targetInput) return;

                if (targetType === 'start') {
                    targetInput.value = place.place_name;

                    const startNameInput = qs('#id_start_place_name');
                    const startLatInput = qs('#id_start_latitude');
                    const startLngInput = qs('#id_start_longitude');

                    if (startNameInput) startNameInput.value = place.place_name;
                    if (startLatInput) startLatInput.value = place.y;
                    if (startLngInput) startLngInput.value = place.x;

                    targetInput.dispatchEvent(new Event('input', { bubbles: true }));
                    closeMap();
                    return;
                }

                const card = targetInput.closest('.place-form-card');

                targetInput.value = place.place_name;

                const latInput = qs('.place-lat', card);
                const lngInput = qs('.place-lng', card);

                if (latInput) latInput.value = place.y;
                if (lngInput) lngInput.value = place.x;

                targetInput.dispatchEvent(new Event('input', { bubbles: true }));
                closeMap();
            });

            fragment.appendChild(li);
        });

        listEl.appendChild(fragment);
    }

    function escapeHtml(value) {
        return String(value)
            .replaceAll('&', '&amp;')
            .replaceAll('<', '&lt;')
            .replaceAll('>', '&gt;')
            .replaceAll('"', '&quot;')
            .replaceAll("'", '&#039;');
    }

    window.removePlace = removePlace;
    window.openMap = openMap;
    window.closeMap = closeMap;
    window.searchPlaces = searchPlaces;
})();