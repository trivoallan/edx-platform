(function (requirejs, require, define) {

// VideoQualityControl module.
define(
'video/05_video_quality_control.js',
[],
function () {

    // VideoQualityControl() function - what this module "exports".
    return function (state) {
        var dfd = $.Deferred();

        // Changing quality for now only works for YouTube videos.
        if (state.videoType !== 'youtube') {
            state.el.find('a.quality_control').remove();
            return;
        }

        state.videoQualityControl = {};

        _makeFunctionsPublic(state);
        _renderElements(state);
        _bindHandlers(state);

        dfd.resolve();
        return dfd.promise();
    };

    // ***************************************************************
    // Private functions start here.
    // ***************************************************************

    // function _makeFunctionsPublic(state)
    //
    //     Functions which will be accessible via 'state' object. When called, these functions will
    //     get the 'state' object as a context.
    function _makeFunctionsPublic(state) {
        var methodsDict = {
            onQualityChange: onQualityChange,
            qualitiesAreAvailable: qualitiesAreAvailable,
            toggleQuality: toggleQuality
        };

        state.bindTo(methodsDict, state.videoQualityControl, state);
    }

    // function _renderElements(state)
    //
    //     Create any necessary DOM elements, attach them, and set their initial configuration. Also
    //     make the created DOM elements available via the 'state' object. Much easier to work this
    //     way - you don't have to do repeated jQuery element selects.
    function _renderElements(state) {
        state.videoQualityControl.el = state.el.find('a.quality_control');

        state.videoQualityControl.el.show();
        state.videoQualityControl.quality = null;
    }

    // function _bindHandlers(state)
    //
    //     Bind any necessary function callbacks to DOM events (click, mousemove, etc.).
    function _bindHandlers(state) {
        state.videoQualityControl.el.on('click', state.videoQualityControl.toggleQuality);
    }

    // ***************************************************************
    // Public functions start here.
    // These are available via the 'state' object. Their context ('this' keyword) is the 'state' object.
    // The magic private function that makes them available and sets up their context is makeFunctionsPublic().
    // ***************************************************************

    function qualitiesAreAvailable() {
        // HD qualities are avaible, enable the HD control.
        if (this.config.hasHDQualities) {
            this.videoQualityControl.el
                                    .removeClass('disabled')
                                    .attr('href', '#');
        }
    }

    function onQualityChange(value) {
        var controlStateStr;
        this.videoQualityControl.quality = value;

        if (_.indexOf(this.config.availableHDQualities, value) !== -1) {
            controlStateStr = gettext('HD on');
            this.videoQualityControl.el
                                    .addClass('active')
                                    .attr('title', controlStateStr)
                                    .text(controlStateStr);
        } else {
            controlStateStr = gettext('HD off');
            this.videoQualityControl.el
                                    .removeClass('active')
                                    .attr('title', controlStateStr)
                                    .text(controlStateStr);

        }
    }

    // This function toggles the quality of video only if HD qualities are
    // available.
    function toggleQuality(event) {
        var newQuality, value = this.videoQualityControl.quality;

        event.preventDefault();

        // The LD and HD qualities are ordered from highest to lowest quality
        // like the array that player.getAvailableQualityLevels() returns.
        if (this.config.hasHDQualities) {
            if (_.contains(this.config.availableLDQualities, value)) {
                newQuality = _.first(this.config.availableHDQualities);
            } else {
                newQuality = _.first(this.config.availableLDQualities);
            }
            this.trigger('videoPlayer.handlePlaybackQualityChange', newQuality);
        }
    }

});

}(RequireJS.requirejs, RequireJS.require, RequireJS.define));
