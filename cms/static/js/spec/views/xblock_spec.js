define([ "jquery", "js/spec_helpers/create_sinon", "URI", "js/views/xblock", "js/models/xblock_info",
    "xmodule", "coffee/src/main", "xblock/cms.runtime.v1"],
    function ($, create_sinon, URI, XBlockView, XBlockInfo) {

        describe("XBlockView", function() {
            var model, xblockView, mockXBlockHtml, respondWithMockXBlockFragment;

            beforeEach(function () {
                model = new XBlockInfo({
                    id: 'testCourse/branch/published/block/verticalFFF',
                    display_name: 'Test Unit',
                    category: 'vertical'
                });
                xblockView = new XBlockView({
                    model: model
                });
            });

            mockXBlockHtml = readFixtures('mock/mock-xblock.underscore');

            respondWithMockXBlockFragment = function(requests, response) {
                var requestIndex = requests.length - 1;
                create_sinon.respondWithJson(requests, response, requestIndex);
            };

            it('can render a nested xblock', function() {
                var requests = create_sinon.requests(this);
                xblockView.render();
                respondWithMockXBlockFragment(requests, {
                    html: mockXBlockHtml,
                    "resources": []
                });

                expect(xblockView.$el.select('.xblock-header')).toBeTruthy();
            });

            describe("XBlock rendering", function() {
                var postXBlockRequest;

                postXBlockRequest = function(requests, resources) {
                    var promise;
                    $.ajax({
                        url: "test_url",
                        type: 'GET',
                        success: function(fragment) {
                            promise = xblockView.renderXBlockFragment(fragment, this.$el);
                        }
                    });
                    // Note: this mock response will call the AJAX success function synchronously
                    // so the promise variable defined above will be available.
                    respondWithMockXBlockFragment(requests, {
                        html: mockXBlockHtml,
                        resources: resources
                    });
                    expect(xblockView.$el.select('.xblock-header')).toBeTruthy();
                    return promise;
                };

                it('can render an xblock with no CSS or JavaScript', function() {
                    var requests = create_sinon.requests(this);
                    postXBlockRequest(requests, []);
                });

                it('can render an xblock with required CSS', function() {
                    var requests = create_sinon.requests(this),
                        mockCssText = "// Just a comment",
                        mockCssUrl = "mock.css",
                        headHtml;
                    postXBlockRequest(requests, [
                        ["hash1", { mimetype: "text/css", kind: "text", data: mockCssText }],
                        ["hash2", { mimetype: "text/css", kind: "url", data: mockCssUrl }]
                    ]);
                    headHtml = $('head').html();
                    expect(headHtml).toContain(mockCssText);
                    expect(headHtml).toContain(mockCssUrl);
                });

                it('can render an xblock with required JavaScript', function() {
                    var requests = create_sinon.requests(this);
                    postXBlockRequest(requests, [
                        ["hash3", { mimetype: "application/javascript", kind: "text", data: "window.test = 100;" }]
                    ]);
                    expect(window.test).toBe(100);
                });

                it('can render an xblock with required HTML', function() {
                    var requests = create_sinon.requests(this),
                        mockHeadTag = "<title>Test Title</title>";
                    postXBlockRequest(requests, [
                        ["hash4", { mimetype: "text/html", placement: "head", data: mockHeadTag }]
                    ]);
                    expect($('head').html()).toContain(mockHeadTag);
                });

                it('aborts rendering when a dependent script fails to load', function() {
                    var requests = create_sinon.requests(this),
                        mockJavaScriptUrl = "mock.js",
                        promise;
                    spyOn($, 'getScript').andReturn($.Deferred().reject().promise());
                    promise = postXBlockRequest(requests, [
                        ["hash5", { mimetype: "application/javascript", kind: "url", data: mockJavaScriptUrl }]
                    ]);
                    expect(promise.isRejected()).toBe(true);
                });
            });
        });
    });
