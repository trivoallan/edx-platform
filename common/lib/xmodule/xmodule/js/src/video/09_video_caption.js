(function (define) {

// VideoCaption module.
define(
'video/09_video_caption.js',
['video/00_sjson.js', 'video/00_async_process.js'],
function (Sjson, AsyncProcess) {
    /**
     * @desc VideoCaption module exports a function.
     *
     * @type {function}
     * @access public
     *
     * @param {object} state - The object containing the state of the video
     *     player. All other modules, their parameters, public variables, etc.
     *     are available via this object.
     *
     * @this {object} The global window object.
     *
     * @returns {object} Return promise.
     */
    var VideoCaption = function (state) {
        if (!(this instanceof VideoCaption)) {
            return new VideoCaption(state);
        }

        this.state = state;
        this.state.videoCaption = this;
        this.renderElements();

        return $.Deferred().resolve().promise();
    };

    VideoCaption.prototype = {
        /**
        * @desc Create any necessary DOM elements, attach them, and set their
        *     initial configuration. Also make the created DOM elements available
        *     via the 'state' object. Much easier to work this way - you don't
        *     have to do repeated jQuery element selects.
        *
        * @type {function}
        * @access public
        *
        * @this {object} - The object containing the state of the video
        *     player. All other modules, their parameters, public variables, etc.
        *     are available via this object.
        *
        * @returns {boolean}
        *     true: The function fetched captions successfully, and completely
        *         rendered everything related to captions.
        *     false: The captions were not fetched. Nothing will be rendered,
        *         and the CC button will be hidden.
        */
        renderElements: function () {
            var state = this.state,
                languages = this.state.config.transcriptLanguages;

            this.loaded = false;
            this.subtitlesEl = state.el.find('ol.subtitles');
            this.container = state.el.find('.lang');
            this.hideSubtitlesEl = state.el.find('a.hide-subtitles');

            if (_.keys(languages).length) {
                this.renderLanguageMenu(languages);

                if (!this.fetchCaption()) {
                    this.hideCaptions(true);
                    this.hideSubtitlesEl.hide();
                }
            } else {
                this.hideCaptions(true, false);
                this.hideSubtitlesEl.hide();
            }
        },
        // function bindHandlers()
        //
        //     Bind any necessary function callbacks to DOM events (click,
        //     mousemove, etc.).
        bindHandlers: function () {
            var self = this,
                state = this.state,
                events = [
                    'mouseover', 'mouseout', 'mousedown', 'click', 'focus', 'blur',
                    'keydown'
                ].join(' ');

            this.hideSubtitlesEl.on('click', this.toggle.bind(this));

            this.subtitlesEl
                .on({
                    mouseenter: this.onMouseEnter.bind(this),
                    mouseleave: this.onMouseLeave.bind(this),
                    mousemove: this.onMovement.bind(this),
                    mousewheel: this.onMovement.bind(this),
                    DOMMouseScroll: this.onMovement.bind(this)
                })
                .on(events, 'li[data-index]', function (event) {
                    switch (event.type) {
                        case 'mouseover':
                        case 'mouseout':
                            self.captionMouseOverOut(event);
                            break;
                        case 'mousedown':
                            self.captionMouseDown(event);
                            break;
                        case 'click':
                            self.captionClick(event);
                            break;
                        case 'focusin':
                            self.captionFocus(event);
                            break;
                        case 'focusout':
                            self.captionBlur(event);
                            break;
                        case 'keydown':
                            self.captionKeyDown(event);
                            break;
                    }
                });

            if (this.showLanguageMenu) {
                this.container.on({
                    mouseenter: this.onContainerMouseEnter,
                    mouseleave: this.onContainerMouseLeave
                });
            }

            state.el
                .on({
                    'caption:fetch': this.fetchCaption,
                    'caption:resize': this.onResize.bind(this),
                    'caption:update': function (event, time) {
                        self.updatePlayTime(time);
                    },
                    'ended': this.pause,
                    'fullscreen': this.onResize.bind(this),
                    'pause': this.pause,
                    'play': this.play,
                });

            if ((state.videoType === 'html5') && (state.config.autohideHtml5)) {
                this.subtitlesEl.on('scroll', state.videoControl.showControls);
            }
        },

        onContainerMouseEnter: function (event) {
            event.preventDefault();

            $(event.currentTarget).addClass('open');
        },

        onContainerMouseLeave: function (event) {
            event.preventDefault();

            $(event.currentTarget).removeClass('open');
        },

        onMouseEnter: function () {
            if (this.frozen) {
                clearTimeout(this.frozen);
            }

            this.frozen = setTimeout(
                this.onMouseLeave,
                this.state.config.captionsFreezeTime
            );
        },

        onMouseLeave: function () {
            if (this.frozen) {
                clearTimeout(this.frozen);
            }

            this.frozen = null;

            if (this.playing) {
                this.scrollCaption();
            }
        },

        onMovement: function () {
            this.onMouseEnter();
        },

        /**
        * @desc Fetch the caption file specified by the user. Upn successful
        *     receival of the file, the captions will be rendered.
        *
        * @type {function}
        * @access public
        *
        * @this {object} - The object containing the state of the video
        *     player. All other modules, their parameters, public variables, etc.
        *     are available via this object.
        *
        * @returns {boolean}
        *     true: The user specified a caption file. NOTE: if an error happens
        *         while the specified file is being retrieved (for example the
        *         file is missing on the server), this function will still return
        *         true.
        *     false: No caption file was specified, or an empty string was
        *         specified.
        */
        fetchCaption: function () {
            var self = this,
                state = this.state,
                language = state.getCurrentLanguage(),
                data;

            if (this.loaded) {
                this.hideCaptions(false);
            } else {
                this.hideCaptions(state.hide_captions, false);
            }

            if (this.fetchXHR && this.fetchXHR.abort) {
                this.fetchXHR.abort();
            }

            if (state.videoType === 'youtube') {
                data = {
                    videoId: state.youtubeId('1.0')
                };
            }

            // Fetch the captions file. If no file was specified, or if an error
            // occurred, then we hide the captions panel, and the "CC" button
            this.fetchXHR = $.ajaxWithPrefix({
                url: state.config.transcriptTranslationUrl + '/' + language,
                notifyOnError: false,
                data: data,
                success: function (sjson) {
                    self.sjson = new Sjson(sjson);

                    var start = self.sjson.getStartTimes(),
                        captions = self.sjson.getCaptions();

                    if (self.loaded) {
                        if (self.rendered) {
                            self.renderCaption(start, captions);
                            self.updatePlayTime(state.videoPlayer.currentTime);
                        }
                    } else {
                        if (state.isTouch) {
                            self.subtitlesEl.find('li').html(
                                gettext(
                                    'Caption will be displayed when ' +
                                    'you start playing the video.'
                                )
                            );
                        } else {
                            self.renderCaption(start, captions);
                        }

                        self.bindHandlers();
                    }

                    self.loaded = true;
                },
                error: function (jqXHR, textStatus, errorThrown) {
                    console.log('[Video info]: ERROR while fetching captions.');
                    console.log(
                        '[Video info]: STATUS:', textStatus +
                        ', MESSAGE:', '' + errorThrown
                    );
                    // If initial list of languages has more than 1 item, check
                    // for availability other transcripts.
                    if (_.keys(state.config.transcriptLanguages).length > 1) {
                        self.fetchAvailableTranslations();
                    } else {
                        self.hideCaptions(true, false);
                        self.hideSubtitlesEl.hide();
                    }
                }
            });

            return true;
        },

        fetchAvailableTranslations: function () {
            var self = this,
                state = this.state;

            return $.ajaxWithPrefix({
                url: state.config.transcriptAvailableTranslationsUrl,
                notifyOnError: false,
                success: function (response) {
                    var currentLanguages = state.config.transcriptLanguages,
                        newLanguages = _.pick(currentLanguages, response);

                    // Update property with available currently translations.
                    state.config.transcriptLanguages = newLanguages;
                    // Remove an old language menu.
                    self.container.find('.langs-list').remove();

                    if (_.keys(newLanguages).length) {
                        // And try again to fetch transcript.
                        self.fetchCaption();
                        self.renderLanguageMenu(newLanguages);
                    }
                },
                error: function (jqXHR, textStatus, errorThrown) {
                    self.hideCaptions(true, false);
                    self.hideSubtitlesEl.hide();
                }
            });
        },

        onResize: function () {
            this.subtitlesEl
                .find('.spacing').first()
                .height(this.topSpacingHeight()).end()
                .find('.spacing').last()
                .height(this.bottomSpacingHeight());

            this.scrollCaption();
            this.setSubtitlesHeight();
        },

        renderLanguageMenu: function (languages) {
            var self = this,
                state = this.state,
                menu = $('<ol class="langs-list menu">'),
                currentLang = state.getCurrentLanguage();

            if (_.keys(languages).length < 2) {
                return false;
            }

            this.showLanguageMenu = true;

            $.each(languages, function(code, label) {
                var li = $('<li data-lang-code="' + code + '" />'),
                    link = $('<a href="javascript:void(0);">' + label + '</a>');

                if (currentLang === code) {
                    li.addClass('active');
                }

                li.append(link);
                menu.append(li);
            });

            this.container.append(menu);

            menu.on('click', 'a', function (e) {
                var el = $(e.currentTarget).parent(),
                    state = self.state,
                    langCode = el.data('lang-code');

                if (state.lang !== langCode) {
                    state.lang = langCode;
                    state.storage.setItem('language', langCode);
                    el  .addClass('active')
                        .siblings('li')
                        .removeClass('active');

                    self.fetchCaption();
                }
            });
        },

        buildCaptions: function  (container, start, captions) {
            var process = function(text, index) {
                    var liEl = $('<li>', {
                        'data-index': index,
                        'data-start': start[index],
                        'tabindex': 0
                    }).html(text);

                    return liEl[0];
                };

            return AsyncProcess.array(captions, process).done(function (list) {
                container.append(list);
            });
        },

        renderCaption: function (start, captions) {
            var self = this;

            var onRender = function () {
                self.addPaddings();
                // Enables or disables automatic scrolling of the captions when the
                // video is playing. This feature has to be disabled when tabbing
                // through them as it interferes with that action. Initially, have
                // this flag enabled as we assume mouse use. Then, if the first
                // caption (through forward tabbing) or the last caption (through
                // backwards tabbing) gets the focus, disable that feature.
                // Re-enable it if tabbing then cycles out of the the captions.
                self.autoScrolling = true;
                // Keeps track of where the focus is situated in the array of
                // captions. Used to implement the automatic scrolling behavior and
                // decide if the outline around a caption has to be hidden or shown
                // on a mouseenter or mouseleave. Initially, no caption has the
                // focus, set the index to -1.
                self.currentCaptionIndex = -1;
                // Used to track if the focus is coming from a click or tabbing. This
                // has to be known to decide if, when a caption gets the focus, an
                // outline has to be drawn (tabbing) or not (mouse click).
                self.isMouseFocus = false;
                self.rendered = true;
            };


            this.rendered = false;
            this.subtitlesEl.empty();
            this.setSubtitlesHeight();
            this.buildCaptions(this.subtitlesEl, start, captions).done(onRender);
        },

        addPaddings: function () {
            // Set top and bottom spacing height and make sure they are taken out of
            // the tabbing order.
            this.subtitlesEl
                .prepend(
                    $('<li class="spacing">')
                        .height(this.topSpacingHeight())
                        .attr('tabindex', -1)
                )
                .append(
                    $('<li class="spacing">')
                        .height(this.bottomSpacingHeight())
                        .attr('tabindex', -1)
                );
        },

        // On mouseOver, hide the outline of a caption that has been tabbed to.
        // On mouseOut, show the outline of a caption that has been tabbed to.
        captionMouseOverOut: function (event) {
            var caption = $(event.target),
                captionIndex = parseInt(caption.attr('data-index'), 10);

            if (captionIndex === this.currentCaptionIndex) {
                if (event.type === 'mouseover') {
                    caption.removeClass('focused');
                }
                else { // mouseout
                    caption.addClass('focused');
                }
            }
        },

        captionMouseDown: function (event) {
            var caption = $(event.target);

            this.isMouseFocus = true;
            this.autoScrolling = true;
            caption.removeClass('focused');
            this.currentCaptionIndex = -1;
        },

        captionClick: function (event) {
            this.seekPlayer(event);
        },

        captionFocus: function (event) {
            var caption = $(event.target),
                captionIndex = parseInt(caption.attr('data-index'), 10);
            // If the focus comes from a mouse click, hide the outline, turn on
            // automatic scrolling and set currentCaptionIndex to point outside of
            // caption list (ie -1) to disable mouseenter, mouseleave behavior.
            if (this.isMouseFocus) {
                this.autoScrolling = true;
                caption.removeClass('focused');
                this.currentCaptionIndex = -1;
            }
            // If the focus comes from tabbing, show the outline and turn off
            // automatic scrolling.
            else {
                this.currentCaptionIndex = captionIndex;
                caption.addClass('focused');
                // The second and second to last elements turn automatic scrolling
                // off again as it may have been enabled in captionBlur.
                if (
                    captionIndex <= 1 ||
                    captionIndex >= this.sjson.getSize() - 2
                ) {
                    this.autoScrolling = false;
                }
            }
        },

        captionBlur: function (event) {
            var caption = $(event.target),
                captionIndex = parseInt(caption.attr('data-index'), 10);

            caption.removeClass('focused');
            // If we are on first or last index, we have to turn automatic scroll
            // on again when losing focus. There is no way to know in what
            // direction we are tabbing. So we could be on the first element and
            // tabbing back out of the captions or on the last element and tabbing
            // forward out of the captions.
            if (captionIndex === 0 ||
                captionIndex === this.sjson.getSize() - 1) {

                this.autoScrolling = true;
            }
        },

        captionKeyDown: function (event) {
            this.isMouseFocus = false;
            if (event.which === 13) { //Enter key
                this.seekPlayer(event);
            }
        },

        scrollCaption: function () {
            var el = this.subtitlesEl.find('.current:first');

            // Automatic scrolling gets disabled if one of the captions has
            // received focus through tabbing.
            if (
                !this.frozen &&
                el.length &&
                this.autoScrolling
            ) {
                this.subtitlesEl.scrollTo(
                    el,
                    {
                        offset: -1 * this.calculateOffset(el)
                    }
                );
            }
        },

        play: function () {
            if (this.loaded) {
                if (!this.rendered) {
                    var start = this.sjson.getStartTimes(),
                        captions = this.sjson.getCaptions();

                    this.renderCaption(start, captions);
                }

                this.playing = true;
            }
        },

        pause: function () {
            if (this.loaded) {
                this.playing = false;
            }
        },

        updatePlayTime: function (time) {
            var state = this.state,
                newIndex;

            if (this.loaded) {
                if (state.isFlashMode()) {
                    time = Time.convert(time, state.speed, '1.0');
                }

                time = Math.round(time * 1000 + 100);
                newIndex = this.sjson.search(time);

                if (
                    typeof newIndex !== 'undefined' &&
                    newIndex !== -1 &&
                    this.currentIndex !== newIndex
                ) {
                    if (typeof this.currentIndex !== 'undefined') {
                        this.subtitlesEl
                            .find('li.current')
                            .removeClass('current');
                    }

                    this.subtitlesEl
                        .find("li[data-index='" + newIndex + "']")
                        .addClass('current');

                    this.currentIndex = newIndex;
                    this.scrollCaption();
                }
            }
        },

        seekPlayer: function (event) {
            var state = this.state,
                time = parseInt($(event.target).data('start'), 10);

            if (state.isFlashMode()) {
                time = Math.round(Time.convert(time, '1.0', state.speed));
            }

            state.trigger(
                'videoPlayer.onCaptionSeek',
                {
                    'type': 'onCaptionSeek',
                    'time': time/1000
                }
            );

            event.preventDefault();
        },

        calculateOffset: function (element) {
            return this.captionHeight() / 2 - element.height() / 2;
        },

        topSpacingHeight: function () {
            return this.calculateOffset(
                this.subtitlesEl.find('li:not(.spacing)').first()
            );
        },

        bottomSpacingHeight: function () {
            return this.calculateOffset(
                this.subtitlesEl.find('li:not(.spacing)').last()
            );
        },

        toggle: function (event) {
            event.preventDefault();

            if (this.state.el.hasClass('closed')) {
                this.hideCaptions(false);
            } else {
                this.hideCaptions(true);
            }
        },

        hideCaptions: function (hide_captions, update_cookie) {
            var hideSubtitlesEl = this.hideSubtitlesEl,
                state = this.state,
                type, text;

            if (typeof update_cookie === 'undefined') {
                update_cookie = true;
            }

            if (hide_captions) {
                type = 'hide_transcript';
                state.captionsHidden = true;
                state.el.addClass('closed');
                text = gettext('Turn on captions');
            } else {
                type = 'show_transcript';
                state.captionsHidden = false;
                state.el.removeClass('closed');
                this.scrollCaption();
                text = gettext('Turn off captions');
            }

            hideSubtitlesEl
                .attr('title', text)
                .text(gettext(text));

            if (state.videoPlayer) {
                state.videoPlayer.log(type, {
                    currentTime: state.videoPlayer.currentTime
                });
            }

            if (state.resizer) {
                if (state.isFullScreen) {
                    state.resizer.setMode('both');
                } else {
                    state.resizer.alignByWidthOnly();
                }
            }

            this.setSubtitlesHeight();
            if (update_cookie) {
                $.cookie('hide_captions', hide_captions, {
                    expires: 3650,
                    path: '/'
                });
            }
        },

        captionHeight: function () {
            var state = this.state;

            if (state.isFullScreen) {
                return state.container.height() - state.videoControl.height;
            } else {
                return state.container.height();
            }
        },

        setSubtitlesHeight: function () {
            var height = 0,
                state = this.state;
            // on page load captionHidden = undefined
            if  ((state.captionsHidden === undefined && state.hide_captions) ||
                state.captionsHidden === true
            ) {
                // In case of html5 autoshowing subtitles, we adjust height of
                // subs, by height of scrollbar.
                height = state.videoControl.el.height() +
                    0.5 * state.videoControl.sliderEl.height();
                // Height of videoControl does not contain height of slider.
                // css is set to absolute, to avoid yanking when slider
                // autochanges its height.
            }

            this.subtitlesEl.css({
                maxHeight: this.captionHeight() - height
            });
        }
    };

    return VideoCaption;
});

}(RequireJS.define));
