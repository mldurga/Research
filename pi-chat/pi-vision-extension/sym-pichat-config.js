/**
 * PI Chat Symbol Configuration Panel
 */

(function (PV) {
    'use strict';

    PV.symbolCatalog.register({
        typeName: 'pichat',

        configOptions: function () {
            return [
                {
                    title: 'Format Symbol',
                    mode: 'format'
                },
                {
                    title: 'Backend Configuration',
                    mode: 'backend'
                }
            ];
        },

        // Configuration template for Format tab
        configTemplateUrl: 'app/editor/symbols/ext/pichat/sym-pichat-config-format.html',

        // Configuration template for Backend tab
        configTemplateUrl2: 'app/editor/symbols/ext/pichat/sym-pichat-config-backend.html'
    });

})(window.PIVisualization);
